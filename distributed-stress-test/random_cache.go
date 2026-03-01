package main

import "math/rand"

var randomCache = make(map[int][]byte)

func getRandomData(size int) []byte {
	if data, ok := randomCache[size]; ok {
		return data
	}
	data := make([]byte, size)
	rand.Read(data)
	randomCache[size] = data
	return data
}
