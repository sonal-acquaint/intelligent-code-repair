<?php

declare(strict_types=1);

namespace Acquaint\AiBugFixer\Tests;

use Acquaint\AiBugFixer\BugFixerServiceProvider;
use Orchestra\Testbench\TestCase as OrchestraTestCase;

abstract class TestCase extends OrchestraTestCase
{
    protected function getPackageProviders($app): array
    {
        return [
            BugFixerServiceProvider::class,
        ];
    }

    protected function defineDatabaseMigrations(): void
    {
        $this->loadMigrationsFrom(__DIR__ . '/../database/migrations');
    }

    protected function defineEnvironment($app): void
    {
        $app['config']->set('database.default', 'testing');
        $app['config']->set('database.connections.testing', [
            'driver' => 'sqlite',
            'database' => ':memory:',
            'prefix' => '',
        ]);
        $app['config']->set('ai-bug-fixer.enabled', true);
        $app['config']->set('ai-bug-fixer.python_url', 'http://127.0.0.1:8001');
    }
}
