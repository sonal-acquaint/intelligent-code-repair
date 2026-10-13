<?php

declare(strict_types=1);

namespace Acquaint\AiBugFixer\Support;

class DataScrubber
{
    /**
     * Sanitize stack trace frames to prevent memory bloat and credential leakage.
     *
     * @param array<int, array<string, mixed>> $trace
     * @return array<int, array<string, mixed>>
     */
    public static function sanitizeTrace(array $trace, int $maxFrames = 15): array
    {
        $sanitized = [];
        $frames = array_slice($trace, 0, $maxFrames);

        foreach ($frames as $frame) {
            $sanitized[] = [
                'file' => $frame['file'] ?? '[internal]',
                'line' => $frame['line'] ?? null,
                'class' => $frame['class'] ?? null,
                'type' => $frame['type'] ?? null,
                'function' => $frame['function'] ?? null,
                'args' => isset($frame['args']) && is_array($frame['args'])
                    ? static::summarizeArgs($frame['args'])
                    : [],
            ];
        }

        return $sanitized;
    }

    /**
     * Recursively mask sensitive fields in arrays (like request payloads).
     */
    public static function scrubArray(array $data, array $scrubFields): array
    {
        $scrubLookup = array_map('strtolower', $scrubFields);

        foreach ($data as $key => $value) {
            $normalizedKey = strtolower((string) $key);

            if (in_array($normalizedKey, $scrubLookup, true)) {
                $data[$key] = '********';
            } elseif (is_array($value)) {
                $data[$key] = static::scrubArray($value, $scrubFields);
            }
        }

        return $data;
    }

    /**
     * Summarize argument types rather than serializing raw values.
     */
    protected static function summarizeArgs(array $args): array
    {
        $summary = [];

        foreach ($args as $arg) {
            if (is_null($arg)) {
                $summary[] = 'null';
            } elseif (is_bool($arg)) {
                $summary[] = $arg ? 'true' : 'false';
            } elseif (is_scalar($arg)) {
                $summary[] = gettype($arg);
            } elseif (is_array($arg)) {
                $summary[] = 'array(' . count($arg) . ')';
            } elseif (is_object($arg)) {
                $summary[] = get_class($arg);
            } elseif (is_resource($arg)) {
                $summary[] = 'resource';
            } else {
                $summary[] = 'unknown';
            }
        }

        return $summary;
    }
}
