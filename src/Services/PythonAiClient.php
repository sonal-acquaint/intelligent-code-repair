<?php

declare(strict_types=1);

namespace Acquaint\AiBugFixer\Services;

use Acquaint\AiBugFixer\Contracts\AiFixClient;
use Illuminate\Support\Facades\Http;
use RuntimeException;

class PythonAiClient implements AiFixClient
{
    /**
     * Send the error payload to the Python AI service for analysis.
     *
     * @param array<string, mixed> $payload
     * @return array<string, mixed>
     */
    public function analyze(array $payload): array
    {
        $baseUrl = rtrim((string) config('ai-bug-fixer.python_url', 'http://127.0.0.1:8001'), '/');
        $endpoint = $baseUrl . '/analyze';

        $timeout = (int) config('ai-bug-fixer.timeout', 60);
        $retries = (int) config('ai-bug-fixer.retries', 2);
        $apiKey = config('ai-bug-fixer.api_key');

        $request = Http::acceptJson()
            ->asJson()
            ->connectTimeout(5)
            ->timeout($timeout);

        if (! empty($apiKey)) {
            $request = $request->withToken($apiKey);
        }

        if ($retries > 0) {
            $request = $request->retry($retries, 500, throw: false);
        }

        $response = $request->post($endpoint, $payload);

        if ($response->failed()) {
            throw new RuntimeException(sprintf(
                'Python AI service error [Status %d]: %s',
                $response->status(),
                $response->body() ?: 'Empty response body'
            ));
        }

        $result = $response->json();

        if (! is_array($result)) {
            throw new RuntimeException('Python AI service returned a non-JSON or invalid array response.');
        }

        return $result;
    }
}