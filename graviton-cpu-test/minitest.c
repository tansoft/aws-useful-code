#define _GNU_SOURCE
#define __USE_GNU
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/time.h>
#include <pthread.h>
#include <sched.h>

void set_use_cpu(int start) {
    cpu_set_t cpuset;
    pthread_t tid = pthread_self();
    CPU_ZERO(&cpuset);
    CPU_SET(start, &cpuset);
    if (pthread_setaffinity_np(tid, sizeof(cpu_set_t), &cpuset) != 0) {
        printf("set addinity error\n");
        exit(1);
    }
}

void *_test(void *arg) {
    static double a=0;
    set_use_cpu(0);
    while(1) {
        for(int i=0;i<10000;i++) {
            a+=1;
            usleep(1);
        }
    }
    return NULL;
}

int main(int argc, char *argv[]) {
    pthread_t tid;
    int test_thread = atoi(argv[1]);
    for(int i=0;i<test_thread;i++){
        pthread_create(&tid, NULL, _test, NULL);
    }
    set_use_cpu(1);
    while(1) {
        sleep(1);
    }
}
