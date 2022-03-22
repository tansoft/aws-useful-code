/*
wget https://raw.githubusercontent.com/tansoft/aws-poc/main/graviton-cpu-test/minirun.c
gcc -lpthread minirun.c -O0 -o minirun
for i in {1..40}; do ./minirun $i; done
*/

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/time.h>

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
    double a=0;
    set_use_cpu(0);
    for(int i=0;i<10000000;i++) {
        a+=1;
    }
    return NULL;
}

int main(int argc, char *argv[]) {
    pthread_t tid[100];
    struct timeval start, end;
    int i, usec;
    int test_thread = atoi(argv[1]);
    for(i=0;i<test_thread;i++){
        pthread_create(&tid[i], NULL, _test, NULL);
    }
    set_use_cpu(1);
    gettimeofday(&start, NULL);
    for(i=0;i<test_thread;i++) {
        pthread_join(tid[i], NULL);
    }
    gettimeofday(&end, NULL);
    usec = (1000000*(end.tv_sec-start.tv_sec)+ end.tv_usec-start.tv_usec);
    printf("%d,%d\n", test_thread, usec);
}
