<?php

declare(strict_types=1);

namespace Acquaint\AiBugFixer\Tests\Unit;

use Acquaint\AiBugFixer\Support\CodeSnippetExtractor;
use Acquaint\AiBugFixer\Tests\TestCase;

class CodeSnippetExtractorTest extends TestCase
{
    public function test_it_extracts_surrounding_lines_correctly(): void
    {
        $tempFile = tempnam(sys_get_temp_dir(), 'test_snippet_');
        $sampleCode = implode("\n", [
            '<?php',
            'line 2',
            'line 3',
            'line 4',
            'line 5 (target error)',
            'line 6',
            'line 7',
        ]);
        file_put_contents($tempFile, $sampleCode);

        try {
            $snippet = CodeSnippetExtractor::extract($tempFile, 5, 2);

            $this->assertCount(5, $snippet);
            $this->assertArrayHasKey(3, $snippet);
            $this->assertArrayHasKey(4, $snippet);
            $this->assertArrayHasKey(5, $snippet);
            $this->assertArrayHasKey(6, $snippet);
            $this->assertArrayHasKey(7, $snippet);
            $this->assertSame('line 5 (target error)', $snippet[5]);
        } finally {
            @unlink($tempFile);
        }
    }

    public function test_it_returns_empty_array_for_invalid_file(): void
    {
        $snippet = CodeSnippetExtractor::extract('/non/existent/path/to/file.php', 10);
        $this->assertSame([], $snippet);
    }
}
