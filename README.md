# Laravel AI Bug Fixer

[![Latest Version on Packagist](https://img.shields.io/packagist/v/acquaint/laravel-ai-bug-fixer.svg?style=flat-square)](https://packagist.org/packages/acquaint/laravel-ai-bug-fixer)
[![Total Downloads](https://img.shields.io/packagist/dt/acquaint/laravel-ai-bug-fixer.svg?style=flat-square)](https://packagist.org/packages/acquaint/laravel-ai-bug-fixer)
[![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](LICENSE.md)

**Laravel AI Bug Fixer** is a production-grade Laravel package that automatically captures application exceptions, extracts sanitized context and code snippets, queues the diagnostic payload, and sends it to a Python-based AI service to analyze root causes and propose code repairs.

---

## Features

- **Automated Exception Capture**: Hooks directly into Laravel's `ExceptionReported` event.
- **Recursion Guard**: Built-in safeguards prevent cascading loops if the analyzer or network fails.
- **Sensitive Data Redaction**: Automatically scrubs credentials, auth tokens, passwords, and sanitizes stack trace objects.
- **Source Code Snippets**: Automatically extracts surrounding code lines (-10 to +10) from the target file to provide rich context to the AI model.
- **Path & Exception Filtering**: Configurable `allowed_paths`, `excluded_paths`, and `ignored_exceptions` (e.g. 404s, validation errors).
- **Asynchronous & Resilient**: Background queue dispatch with exponential backoff and retries.
- **Developer CLI Tooling**: Built-in `php artisan ai-bug-fixer:test` to verify connectivity to your Python service.

---

## Installation

You can install the package via Composer:

```bash
composer require acquaint/laravel-ai-bug-fixer
```

Publish the package configuration file:

```bash
php artisan vendor:publish --tag=ai-bug-fixer-config
```

---

## Configuration

The published configuration file is located at `config/ai-bug-fixer.php`. You can configure the following environment variables in your `.env` file:

```env
# Enable or disable AI error tracking
AI_BUG_FIXER_ENABLED=true

# Python AI service endpoint
AI_BUG_FIXER_PYTHON_URL=http://127.0.0.1:8001

# Optional API key for authenticating with your Python service
AI_BUG_FIXER_API_KEY=your-secret-api-key

# Request timeout in seconds
AI_BUG_FIXER_TIMEOUT=60

# Retries on network failure
AI_BUG_FIXER_RETRIES=2

# Queue name for asynchronous processing
AI_BUG_FIXER_QUEUE=ai-bug-fixes
```

---

## Verifying Connectivity

You can test that your Laravel application can communicate with the Python AI endpoint using the Artisan command:

```bash
php artisan ai-bug-fixer:test
```

---

## Payload Specification (Laravel -> Python API)

The package sends a `POST` request to `{AI_BUG_FIXER_PYTHON_URL}/analyze` with a JSON payload structured as follows:

```json
{
  "id": "c1f727f6-6b2a-4ce6-a791-3e0e9a7e0a2b",
  "timestamp": "2026-10-12T10:00:00+00:00",
  "exception_class": "App\\Exceptions\\OrderProcessingException",
  "message": "Payment gateway timeout on transaction",
  "code": 504,
  "file": "/var/www/html/app/Services/PaymentService.php",
  "relative_file": "app/Services/PaymentService.php",
  "line": 42,
  "code_snippet": {
    "38": "    public function process(Order $order): void",
    "39": "    {",
    "40": "        $gateway = $this->gatewayFactory->make();",
    "41": "",
    "42": "        $response = $gateway->charge($order->total);",
    "43": "    }"
  },
  "trace": [
    {
      "file": "/var/www/html/app/Http/Controllers/CheckoutController.php",
      "line": 28,
      "class": "App\\Services\\PaymentService",
      "type": "->",
      "function": "process",
      "args": ["App\\Models\\Order"]
    }
  ],
  "environment": "production",
  "laravel_version": "12.0.0",
  "php_version": "8.4.0",
  "context": {
    "type": "http",
    "http": {
      "method": "POST",
      "url": "https://example.com/checkout",
      "full_url": "https://example.com/checkout?step=2",
      "route_name": "checkout.process",
      "route_action": "App\\Http\\Controllers\\CheckoutController@process",
      "ip": "192.168.1.1",
      "headers": {
        "user-agent": "Mozilla/5.0 ...",
        "accept": "application/json"
      },
      "input": {
        "order_id": 1054,
        "payment_method": "stripe",
        "card_number": "********"
      }
    }
  }
}
```

### Expected Python API Response

Your Python API service should respond with HTTP status `200` and a JSON body:

```json
{
  "status": "fix_available",
  "summary": "Handled network timeout by adding retry wrapper around gateway charge.",
  "fixes": [
    {
      "file": "app/Services/PaymentService.php",
      "diff": "--- a/PaymentService.php\n+++ b/PaymentService.php\n@@ -42,1 +42,3 @@\n-$response = $gateway->charge($order->total);\n+retry(3, function () use ($gateway, $order) {\n+    return $gateway->charge($order->total);\n+});"
    }
  ]
}
```

Supported `status` values:
- `fix_available`: Fixes proposed and returned.
- `needs_more_context`: More information or code needed.
- `no_fix_found`: Analysis complete, no automatic fix identified.
- `error`: Analysis encountered an error.

---

## Testing

Run unit and feature tests:

```bash
composer test
```

Or directly via PHPUnit:

```bash
./vendor/bin/phpunit
```

---

## License

The MIT License (MIT). Please see [License File](LICENSE.md) for more information.
