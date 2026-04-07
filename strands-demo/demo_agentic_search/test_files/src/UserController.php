<?php

namespace App\Controllers;

use App\Models\User;
use App\Services\AuthService;

class UserController extends BaseController
{
    private AuthService $authService;

    public function __construct(AuthService $authService)
    {
        $this->authService = $authService;
    }

    public function login(Request $request): Response
    {
        $email = $request->input('email');
        $password = $request->input('password');
        $token = $this->authService->authenticate($email, $password);
        return response()->json(['token' => $token]);
    }

    public function getProfile(int $userId): Response
    {
        $user = User::findOrFail($userId);
        return response()->json($user->toArray());
    }

    public function updateProfile(Request $request, int $userId): Response
    {
        $user = User::findOrFail($userId);
        $user->update($request->validated());
        return response()->json(['status' => 'updated']);
    }
}
