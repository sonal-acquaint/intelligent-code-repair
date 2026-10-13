<?php

declare(strict_types=1);

namespace Acquaint\AiBugFixer;

use Acquaint\AiBugFixer\Commands\TestConnectionCommand;
use Acquaint\AiBugFixer\Contracts\AiFixClient;
use Acquaint\AiBugFixer\Listeners\CaptureReportedException;
use Acquaint\AiBugFixer\Services\PythonAiClient;
use Illuminate\Contracts\Debug\ExceptionHandler;
use Illuminate\Support\ServiceProvider;
use Throwable;

class BugFixerServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        $this->mergeConfigFrom(
            __DIR__ . '/../config/ai-bug-fixer.php',
            'ai-bug-fixer'
        );

        $this->app->singleton(
            AiFixClient::class,
            PythonAiClient::class
        );
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        $this->loadMigrationsFrom(__DIR__ . '/../database/migrations');

        if ($this->app->runningInConsole()) {
            $this->publishes([
                __DIR__ . '/../config/ai-bug-fixer.php' => config_path('ai-bug-fixer.php'),
            ], ['ai-bug-fixer-config', 'config']);

            $this->publishes([
                __DIR__ . '/../database/migrations' => database_path('migrations'),
            ], ['ai-bug-fixer-migrations', 'migrations']);

            $this->commands([
                TestConnectionCommand::class,
            ]);
        }

        $this->registerExceptionHandler();
    }

    /**
     * Register the exception handler callback.
     */
    protected function registerExceptionHandler(): void
    {
        if ($this->app->bound(ExceptionHandler::class)) {
            $handler = $this->app->make(ExceptionHandler::class);

            if (method_exists($handler, 'reportable')) {
                $handler->reportable(function (Throwable $e) {
                    $this->app->make(CaptureReportedException::class)->handle($e);
                });
            }
        }
    }
}
