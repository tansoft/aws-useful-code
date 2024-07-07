
func addOrMoveToFront(gameList []model.GameCollectionInfo, recentGame *model.GameCollectionInfo) []model.GameCollectionInfo {
    // Find the index of recentGame in the list
    index := -1
    for i, game := range gameList {
        if game.GameId == recentGame.GameId {
            index = i
            break
        }
    }
    // If recentGame is found, remove it from its current position
    if index != -1 {
        gameList = append(gameList[:index], gameList[index+1:]...)
    }
    // Prepend recentGame to the front of the list
    gameList = append([]model.GameCollectionInfo{*recentGame}, gameList...)
    return gameList
}

