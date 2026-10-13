<?php

declare(strict_types=1);

namespace Acquaint\AiBugFixer\Jobs;

use Acquaint\AiBugFixer\Contracts\AiFixClient;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Log;
use Throwable;
use Acquaint\AiBugFixer\Models\AiError;
use UnexpectedValueException;

class AnalyzeErrorJob implements ShouldQueue
{
    use Dispatchable;
    use InteractsWithQueue;
    use Queueable;
    use SerializesModels;

    public int $tries = 3;

    public array $backoff = [10, 30, 60];

    public int $timeout = 90;

    public function __construct(
        public array $payload,
        public ?int $errorRecordId = null
    ) {}

    public function handle(AiFixClient $client): void
    {
        if ($this->errorRecordId) {
            try {
                AiError::where('id', $this->errorRecordId)->update(['status' => 'analyzing']);
            } catch (Throwable) {
                // Ignore DB error during status update
            }
        }

        try {
            $result = $client->analyze($this->payload);

            $this->validateResult($result);

            if ($this->errorRecordId) {
                try {
                    AiError::where('id', $this->errorRecordId)->update([
                        'status' => $result['status'] ?? 'unknown',
                        'ai_summary' => $result['summary'] ?? null,
                        'ai_fixes' => $result['fixes'] ?? null,
                    ]);
                } catch (Throwable) {
                    // Ignore DB error during update
                }
            }

            Log::info('AI Bug Fixer analysis completed.', [
                'error_id' => $this->payload['id'] ?? null,
                'record_id' => $this->errorRecordId,
                'exception' => $this->payload['exception_class'] ?? null,
                'status' => $result['status'] ?? 'unknown',
                'summary' => $result['summary'] ?? null,
                'fix_count' => count($result['fixes'] ?? []),
            ]);
        } catch (Throwable $exception) {
            Log::warning('AI Bug Fixer analysis attempt failed.', [
                'error_id' => $this->payload['id'] ?? null,
                'record_id' => $this->errorRecordId,
                'exception' => get_class($exception),
                'message' => $exception->getMessage(),
                'attempt' => $this->attempts(),
            ]);

            throw $exception;
        }
    }

    /**
     * Handle a job failure after exhausting all retries.
     */
    public function failed(?Throwable $exception): void
    {
        if ($this->errorRecordId) {
            try {
                AiError::where('id', $this->errorRecordId)->update([
                    'status' => 'error',
                    'ai_summary' => $exception ? $exception->getMessage() : 'Job failed',
                ]);
            } catch (Throwable) {
                // Ignore DB error during failure update
            }
        }

        Log::error('AI Bug Fixer job exhausted all retry attempts.', [
            'error_id' => $this->payload['id'] ?? null,
            'record_id' => $this->errorRecordId,
            'exception' => $exception ? get_class($exception) : null,
            'message' => $exception ? $exception->getMessage() : null,
        ]);
    }

    /**
     * Validate the response received from the Python AI service.
     */
    protected function validateResult(array $result): void
    {
        $allowedStatuses = [
            'fix_available',
            'needs_more_context',
            'no_fix_found',
            'error',
        ];

        if (! in_array($result['status'] ?? null, $allowedStatuses, true)) {
            throw new UnexpectedValueException(
                sprintf('Python AI service returned an unsupported status: %s', $result['status'] ?? 'null')
            );
        }

        if (isset($result['fixes']) && ! is_array($result['fixes'])) {
            throw new UnexpectedValueException('Python AI service returned an invalid fixes field.');
        }
    }
}