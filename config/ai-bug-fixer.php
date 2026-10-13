<?php

return [
    /*
    |--------------------------------------------------------------------------
    | Enable / Disable AI Bug Fixer
    |--------------------------------------------------------------------------
    |
    | When enabled, uncaught exceptions reported by Laravel will be analyzed
    | and queued to send to the Python AI service.
    |
    */
    'enabled' => (bool) env('AI_BUG_FIXER_ENABLED', false),

    /*
    |--------------------------------------------------------------------------
    | Python AI API URL & Secret
    |--------------------------------------------------------------------------
    |
    | The base URL and optional API key for the Python AI error repair service.
    |
    */
    'python_url' => env('AI_BUG_FIXER_PYTHON_URL', 'http://127.0.0.1:8001'),

    'api_key' => env('AI_BUG_FIXER_API_KEY', null),

    /*
    |--------------------------------------------------------------------------
    | HTTP Client Timeout & Retries
    |--------------------------------------------------------------------------
    |
    | Maximum number of seconds to wait when sending payloads to the Python API.
    |
    */
    'timeout' => 60,

    'retries' => 2,

    /*
    |--------------------------------------------------------------------------
    | Queue Configuration
    |--------------------------------------------------------------------------
    |
    | The queue connection and queue name where error analysis jobs should be dispatched.
    |
    */
    'queue' => env('AI_BUG_FIXER_QUEUE', 'ai-bug-fixes'),

    'queue_connection' => env('AI_BUG_FIXER_QUEUE_CONNECTION', null),

    /*
    |--------------------------------------------------------------------------
    | Auto-Apply Proposed Fixes
    |--------------------------------------------------------------------------
    |
    | When true, fixes proposed by the AI service may be applied automatically.
    | Kept false by default to ensure review before modifying code.
    |
    */
    'auto_apply' => (bool) env('AI_BUG_FIXER_AUTO_APPLY', false),

    /*
    |--------------------------------------------------------------------------
    | Allowed Paths
    |--------------------------------------------------------------------------
    |
    | Only exceptions whose originating file starts with one of these paths
    | will be captured. Set to empty array to allow all project paths.
    |
    */
    'allowed_paths' => [
        'app/',
    ],

    /*
    |--------------------------------------------------------------------------
    | Excluded Paths
    |--------------------------------------------------------------------------
    |
    | Exceptions originating in these paths or files are ignored.
    |
    */
    'excluded_paths' => [
        '.env',
        'vendor/',
        'storage/',
        'bootstrap/cache/',
        'node_modules/',
    ],

    /*
    |--------------------------------------------------------------------------
    | Ignored Exceptions
    |--------------------------------------------------------------------------
    |
    | Common user or benign HTTP exceptions that should never be sent to the AI.
    |
    */
    'ignored_exceptions' => [
        \Symfony\Component\HttpKernel\Exception\NotFoundHttpException::class,
        \Illuminate\Validation\ValidationException::class,
        \Illuminate\Auth\AuthenticationException::class,
        \Illuminate\Auth\Access\AuthorizationException::class,
        \Illuminate\Session\TokenMismatchException::class,
        \Symfony\Component\HttpKernel\Exception\AccessDeniedHttpException::class,
    ],

    /*
    |--------------------------------------------------------------------------
    | Data Scrubbing / Sensitive Fields
    |--------------------------------------------------------------------------
    |
    | Field keys in requests or stack traces whose values should be masked
    | to prevent leaking credentials or PII to the AI service.
    |
    */
    'scrub_fields' => [
        'password',
        'password_confirmation',
        'secret',
        'token',
        'authorization',
        'cookie',
        'api_key',
        'card_number',
        'cvv',
        'ssn',
    ],

    /*
    |--------------------------------------------------------------------------
    | Source Code Snippet Context
    |--------------------------------------------------------------------------
    |
    | Number of lines before and after the offending line of code to include
    | in the payload for the AI model to read the surrounding context.
    |
    */
    'context_lines' => 10,

    /*
    |--------------------------------------------------------------------------
    | Capture Request Context
    |--------------------------------------------------------------------------
    |
    | When true, the current HTTP request details (URL, method, route, sanitized inputs)
    | will be attached to the error payload.
    |
    */
    'send_request_context' => true,
];