<?php

declare(strict_types=1);

namespace Acquaint\AiBugFixer\Listeners;

use Acquaint\AiBugFixer\Jobs\AnalyzeErrorJob;
use Acquaint\AiBugFixer\Support\CodeSnippetExtractor;
use Acquaint\AiBugFixer\Support\DataScrubber;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;
use Throwable;

class CaptureReportedException
{
    /**
     * Guard against recursive exception handling loops.
     */
    public static bool $isHandling = false;

    public function handle(mixed $exception): void
    {
        if (! config('ai-bug-fixer.enabled', false)) {
            return;
        }

        if (static::$isHandling) {
            return;
        }

        if (! $exception instanceof Throwable) {
            $exception = $exception->exception ?? null;
        }

        if (! $exception instanceof Throwable) {
            return;
        }

        // Avoid capturing exceptions thrown by this package itself
        if (str_starts_with(get_class($exception), 'Acquaint\\AiBugFixer\\')) {
            return;
        }

        // Check against ignored exception types
        if ($this->isIgnoredException($exception)) {
            return;
        }

        // Check against allowed and excluded file paths
        if (! $this->isPathAllowed($exception->getFile())) {
            return;
        }

        static::$isHandling = true;

        try {
            $payload = $this->buildPayload($exception);

            $job = AnalyzeErrorJob::dispatch($payload);

            $queue = config('ai-bug-fixer.queue');
            if ($queue) {
                $job->onQueue($queue);
            }

            $connection = config('ai-bug-fixer.queue_connection');
            if ($connection) {
                $job->onConnection($connection);
            }
        } catch (Throwable $dispatchError) {
            // Never let the AI package disrupt standard error reporting
            Log::warning('AI Bug Fixer could not queue an error.', [
                'exception' => get_class($dispatchError),
                'message' => $dispatchError->getMessage(),
            ]);
        } finally {
            static::$isHandling = false;
        }
    }

    /**
     * Determine if the exception is in the ignored list.
     */
    protected function isIgnoredException(Throwable $exception): bool
    {
        $ignored = (array) config('ai-bug-fixer.ignored_exceptions', []);

        foreach ($ignored as $ignoredClass) {
            if ($exception instanceof $ignoredClass) {
                return true;
            }
        }

        return false;
    }

    /**
     * Determine whether the originating file is allowed according to path rules.
     */
    protected function isPathAllowed(string $filePath): bool
    {
        $basePath = function_exists('base_path') ? base_path() : '';
        $normalizedFile = str_replace('\\', '/', $filePath);
        $normalizedBase = str_replace('\\', '/', $basePath);

        // Compute relative path if possible
        $relativePath = $normalizedFile;
        if ($basePath && str_starts_with($normalizedFile, $normalizedBase)) {
            $relativePath = ltrim(substr($normalizedFile, strlen($normalizedBase)), '/');
        }

        $excludedPaths = (array) config('ai-bug-fixer.excluded_paths', []);
        foreach ($excludedPaths as $excluded) {
            $normalizedExcluded = trim(str_replace('\\', '/', $excluded), '/');
            if ($normalizedExcluded !== '' && str_contains($relativePath, $normalizedExcluded)) {
                return false;
            }
        }

        $allowedPaths = (array) config('ai-bug-fixer.allowed_paths', []);
        if (empty($allowedPaths)) {
            return true;
        }

        foreach ($allowedPaths as $allowed) {
            $normalizedAllowed = trim(str_replace('\\', '/', $allowed), '/');
            if ($normalizedAllowed !== '' && str_starts_with($relativePath, $normalizedAllowed)) {
                return true;
            }
        }

        return false;
    }

    /**
     * Build the structured error payload for the Python AI service.
     */
    protected function buildPayload(Throwable $exception): array
    {
        $scrubFields = (array) config('ai-bug-fixer.scrub_fields', []);
        $contextLines = (int) config('ai-bug-fixer.context_lines', 10);
        $filePath = $exception->getFile();
        $basePath = function_exists('base_path') ? base_path() : '';

        $relativeFile = $filePath;
        if ($basePath && str_starts_with($filePath, $basePath)) {
            $relativeFile = ltrim(substr($filePath, strlen($basePath)), '/\\');
        }

        $payload = [
            'id' => (string) Str::uuid(),
            'timestamp' => now()->toIso8601String(),
            'exception_class' => get_class($exception),
            'message' => $exception->getMessage(),
            'code' => $exception->getCode(),
            'file' => $filePath,
            'relative_file' => $relativeFile,
            'line' => $exception->getLine(),
            'code_snippet' => CodeSnippetExtractor::extract($filePath, $exception->getLine(), $contextLines),
            'trace' => DataScrubber::sanitizeTrace($exception->getTrace()),
            'environment' => app()->environment(),
            'laravel_version' => app()->version(),
            'php_version' => PHP_VERSION,
        ];

        if (config('ai-bug-fixer.send_request_context', true)) {
            $payload['context'] = $this->collectContext($scrubFields);
        }

        return $payload;
    }

    /**
     * Safely collect HTTP or CLI context without sensitive data.
     */
    protected function collectContext(array $scrubFields): array
    {
        $context = [
            'type' => app()->runningInConsole() ? 'cli' : 'http',
        ];

        if (app()->runningInConsole()) {
            $context['command'] = $_SERVER['argv'] ?? [];
            return $context;
        }

        if (app()->bound('request')) {
            $request = request();
            $route = $request->route();

            $context['http'] = [
                'method' => $request->method(),
                'url' => $request->url(),
                'full_url' => $request->fullUrl(),
                'route_name' => is_object($route) && method_exists($route, 'getName') ? $route->getName() : null,
                'route_action' => is_object($route) && method_exists($route, 'getActionName') ? $route->getActionName() : null,
                'ip' => $request->ip(),
                'headers' => [
                    'user-agent' => $request->userAgent(),
                    'accept' => $request->header('accept'),
                ],
                'input' => DataScrubber::scrubArray($request->except(['_token']), $scrubFields),
            ];
        }

        return $context;
    }
}