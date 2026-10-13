<?php

declare(strict_types=1);

namespace Acquaint\AiBugFixer\Tests\Unit;

use Acquaint\AiBugFixer\Support\DataScrubber;
use Acquaint\AiBugFixer\Tests\TestCase;

class DataScrubberTest extends TestCase
{
    public function test_it_scrubs_sensitive_keys_recursively(): void
    {
        $payload = [
            'username' => 'john_doe',
            'password' => 'secret123',
            'nested' => [
                'token' => 'jwt.token.here',
                'api_key' => 'xyz-999',
                'safe_field' => 'ok',
            ],
        ];

        $scrubbed = DataScrubber::scrubArray($payload, ['password', 'token', 'api_key']);

        $this->assertSame('john_doe', $scrubbed['username']);
        $this->assertSame('********', $scrubbed['password']);
        $this->assertSame('********', $scrubbed['nested']['token']);
        $this->assertSame('********', $scrubbed['nested']['api_key']);
        $this->assertSame('ok', $scrubbed['nested']['safe_field']);
    }

    public function test_it_sanitizes_stack_traces_without_raw_arguments(): void
    {
        $rawTrace = [
            [
                'file' => '/app/Services/UserService.php',
                'line' => 42,
                'function' => 'login',
                'class' => 'App\\Services\\UserService',
                'type' => '->',
                'args' => ['user@example.com', 'mypassword', ['token' => '123']],
            ],
        ];

        $sanitized = DataScrubber::sanitizeTrace($rawTrace);

        $this->assertCount(1, $sanitized);
        $this->assertSame('/app/Services/UserService.php', $sanitized[0]['file']);
        $this->assertSame(42, $sanitized[0]['line']);
        $this->assertSame('login', $sanitized[0]['function']);
        $this->assertSame(['string', 'string', 'array(1)'], $sanitized[0]['args']);
    }
}
