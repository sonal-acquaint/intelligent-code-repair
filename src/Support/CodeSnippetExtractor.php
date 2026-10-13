<?php

declare(strict_types=1);

namespace Acquaint\AiBugFixer\Support;

class CodeSnippetExtractor
{
    /**
     * Extract surrounding lines of code around the target line.
     *
     * @return array<int, string> Associative array of line_number => code
     */
    public static function extract(string $filePath, int $targetLine, int $contextLines = 10): array
    {
        if (! is_file($filePath) || ! is_readable($filePath)) {
            return [];
        }

        $lines = @file($filePath);
        if ($lines === false) {
            return [];
        }

        $totalLines = count($lines);
        $start = max(1, $targetLine - $contextLines);
        $end = min($totalLines, $targetLine + $contextLines);

        $snippet = [];
        for ($i = $start; $i <= $end; $i++) {
            $snippet[$i] = rtrim($lines[$i - 1], "\r\n");
        }

        return $snippet;
    }
}
