


gameHistory, err := GetUserGameHistory(ctx, userID)
 if err != nil {
    logger.Error("GetRecentGame err:", err)
}
