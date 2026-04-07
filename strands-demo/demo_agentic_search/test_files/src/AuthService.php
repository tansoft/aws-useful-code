<?php

namespace App\Services;

use App\Models\User;
use Firebase\JWT\JWT;

class AuthService
{
    private string $jwtSecret;

    public function __construct(string $jwtSecret)
    {
        $this->jwtSecret = $jwtSecret;
    }

    public function authenticate(string $email, string $password): string
    {
        $user = User::where('email', $email)->first();
        if (!$user || !password_verify($password, $user->password)) {
            throw new \RuntimeException('Invalid credentials');
        }
        return $this->generateToken($user);
    }

    private function generateToken(User $user): string
    {
        $payload = [
            'sub' => $user->id,
            'email' => $user->email,
            'exp' => time() + 3600,
        ];
        return JWT::encode($payload, $this->jwtSecret, 'HS256');
    }
}
