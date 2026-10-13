<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        if (! Schema::hasTable('ai_bug_fixer_errors')) {
            Schema::create('ai_bug_fixer_errors', function (Blueprint $table) {
                $table->id();
                $table->uuid('uuid')->unique();
                $table->string('error_hash', 64)->index();
                $table->string('exception_class');
                $table->text('message');
                $table->string('file');
                $table->integer('line');
                $table->unsignedInteger('occurrences_count')->default(1);
                $table->string('status', 32)->default('pending')->index();
                $table->text('ai_summary')->nullable();
                $table->json('ai_fixes')->nullable();
                $table->json('payload')->nullable();
                $table->timestamp('last_seen_at')->nullable();
                $table->timestamps();
            });
        }
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('ai_bug_fixer_errors');
    }
};
