<?php

namespace Acquaint\AiBugFixer\Contracts;

interface AiFixClient
{
    public function analyze(array $payload): array;
}