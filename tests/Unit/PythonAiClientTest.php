<?php

declare(strict_types=1);

namespace Acquaint\AiBugFixer\Tests\Unit;

use Acquaint\AiBugFixer\Services\PythonAiClient;
use Acquaint\AiBugFixer\Tests\TestCase;
use Illuminate\Support\Facades\Http;
use RuntimeException;

class PythonAiClientTest extends TestCase
{
    public function test_it_sends_payload_successfully_to_python_service(): void
    {
        Http::fake([
            'http://127.0.0.1:8001/analyze' => Http::response([
                'status' => 'fix_available',
                'summary' => 'Fixed null pointer access',
                'fixes' => [
                    [
                        'file' => 'app/Services/TestService.php',
                        'diff' => '--- a/TestService.php\n+++ b/TestService.php',
                    ],
                ],
            ], 200),
        ]);

        $client = new PythonAiClient();
        $response = $client->analyze([
            'message' => 'Undefined variable $user',
            'file' => 'app/Services/TestService.php',
            'line' => 20,
        ]);

        $this->assertSame('fix_available', $response['status']);
        $this->assertCount(1, $response['fixes']);
    }

    public function test_it_throws_exception_when_python_service_fails(): void
    {
        Http::fake([
            'http://127.0.0.1:8001/analyze' => Http::response([
                'error' => 'Internal AI model error',
            ], 500),
        ]);

        $this->expectException(RuntimeException::class);

        $client = new PythonAiClient();
        $client->analyze(['dummy' => 'payload']);
    }
}
