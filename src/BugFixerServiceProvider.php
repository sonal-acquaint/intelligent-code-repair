<?php

namespace Acquaint\LaravelAiBugFixer;

use Illuminate\Support\ServiceProvider;

class BugFixerServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->mergeConfigFrom(
            __DIR__ . '/../config/ai-bug-fixer.php',
            'ai-bug-fixer'
        );
    }

    public function boot(): void
    {
        $this->publishes([
            __DIR__ . '/../config/ai-bug-fixer.php' => config_path('ai-bug-fixer.php'),
        ], 'ai-bug-fixer-config');
    }
}
