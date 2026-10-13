<?php

declare(strict_types=1);

namespace Acquaint\AiBugFixer\Tests\Feature;

use Acquaint\AiBugFixer\Contracts\AiFixClient;
use Acquaint\AiBugFixer\Jobs\AnalyzeErrorJob;
use Acquaint\AiBugFixer\Models\AiError;
use Acquaint\AiBugFixer\Tests\TestCase;
use Exception;
use Mockery;

class AnalyzeErrorJobTest extends TestCase
{
    public function test_it_updates_database_record_on_successful_analysis(): void
    {
        $record = AiError::create([
            'uuid' => 'test-uuid-1234',
            'error_hash' => 'hash123',
            'exception_class' => Exception::class,
            'message' => 'Test error',
            'file' => 'app/Services/TestService.php',
            'line' => 25,
            'status' => 'pending',
            'payload' => ['id' => 'test-uuid-1234'],
        ]);

        $mockClient = Mockery::mock(AiFixClient::class);
        $mockClient->shouldReceive('analyze')
            ->once()
            ->andReturn([
                'status' => 'fix_available',
                'summary' => 'Fixed null pointer by adding null coalescing operator.',
                'fixes' => [
                    [
                        'file' => 'app/Services/TestService.php',
                        'diff' => '--- a/TestService.php\n+++ b/TestService.php\n@@ -25,1 +25,1 @@\n-$val = $user->name;\n+$val = $user?->name ?? "Guest";',
                    ],
                ],
            ]);

        $job = new AnalyzeErrorJob(['id' => 'test-uuid-1234'], $record->id);
        $job->handle($mockClient);

        $record->refresh();
        $this->assertEquals('fix_available', $record->status);
        $this->assertEquals('Fixed null pointer by adding null coalescing operator.', $record->ai_summary);
        $this->assertCount(1, $record->ai_fixes);
    }
}
