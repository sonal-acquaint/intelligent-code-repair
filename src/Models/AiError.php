<?php

declare(strict_types=1);

namespace Acquaint\AiBugFixer\Models;

use Illuminate\Database\Eloquent\Model;

class AiError extends Model
{
    /**
     * The attributes that aren't mass assignable.
     *
     * @var array<string>|bool
     */
    protected $guarded = [];

    /**
     * The attributes that should be cast.
     *
     * @var array<string, string>
     */
    protected $casts = [
        'line' => 'integer',
        'occurrences_count' => 'integer',
        'ai_fixes' => 'array',
        'payload' => 'array',
        'last_seen_at' => 'datetime',
    ];

    /**
     * The table associated with the model.
     *
     * @var string
     */
    protected $table = 'ai_bug_fixer_errors';
}
