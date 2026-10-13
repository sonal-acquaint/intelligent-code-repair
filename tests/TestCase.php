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

    protected function defineEnvironment($app): void
    {
        $app['config']->set('ai-bug-fixer.enabled', true);
        $app['config']->set('ai-bug-fixer.python_url', 'http://127.0.0.1:8001');
    }
}
