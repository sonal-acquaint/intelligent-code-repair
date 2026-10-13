<?php

declare(strict_types=1);

namespace Acquaint\AiBugFixer\Tests\Feature;

use Acquaint\AiBugFixer\Jobs\AnalyzeErrorJob;
use Acquaint\AiBugFixer\Listeners\CaptureReportedException;
use Acquaint\AiBugFixer\Tests\TestCase;
use Exception;
use Illuminate\Support\Facades\Queue;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

class CaptureReportedExceptionTest extends TestCase
{
    public function test_it_dispatches_job_when_allowed_exception_is_reported(): void
    {
        Queue::fake();

        config()->set('ai-bug-fixer.enabled', true);
        config()->set('ai-bug-fixer.allowed_paths', []); // allow all for test
        config()->set('ai-bug-fixer.excluded_paths', []);

        $exception = new Exception('Test system failure');

        $listener = new CaptureReportedException();
        $listener->handle($exception);

        Queue::assertPushed(AnalyzeErrorJob::class, function (AnalyzeErrorJob $job) {
            return $job->payload['message'] === 'Test system failure'
                && $job->payload['exception_class'] === Exception::class;
        });
    }

    public function test_it_captures_exceptions_reported_via_laravel_report_helper(): void
    {
        Queue::fake();

        config()->set('ai-bug-fixer.enabled', true);
        config()->set('ai-bug-fixer.allowed_paths', []);
        config()->set('ai-bug-fixer.excluded_paths', []);

        $exception = new Exception('Error via report() helper');
        report($exception);

        Queue::assertPushed(AnalyzeErrorJob::class, function (AnalyzeErrorJob $job) {
            return $job->payload['message'] === 'Error via report() helper';
        });
    }

    public function test_it_ignores_configured_ignored_exceptions(): void
    {
        Queue::fake();

        config()->set('ai-bug-fixer.enabled', true);

        $exception = new NotFoundHttpException('Resource not found');

        $listener = new CaptureReportedException();
        $listener->handle($exception);

        Queue::assertNothingPushed();
    }

    public function test_it_does_not_dispatch_when_disabled(): void
    {
        Queue::fake();

        config()->set('ai-bug-fixer.enabled', false);

        $exception = new Exception('Some failure');

        $listener = new CaptureReportedException();
        $listener->handle($exception);

        Queue::assertNothingPushed();
    }
}
