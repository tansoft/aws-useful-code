#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/time.h>

typedef struct _cpu_info
{
    char name[20];
    unsigned int user;
    unsigned int nice;
    unsigned int system;
    unsigned int idle;
    unsigned int iowait;
    unsigned int irq;
    unsigned int softirq;
}cpu_info_t;

int get_cpu_occupy(int cpu_index,cpu_info_t* info)
{
    FILE* fp = NULL;
    char key[10] = {0};
    char buf[256] = {0};
    int ret = 1;

    sprintf(key, "cpu%d", cpu_index);

    fp = fopen("/proc/stat", "r");
    while(fgets(buf, sizeof(buf), fp)) {
        sscanf(buf, "%s %u %u %u %u %u %u %u", info->name, &info->user, &info->nice, 
            &info->system, &info->idle, &info->iowait, &info->irq, &info->softirq);
        if (strcmp(info->name, key) == 0) {
            ret = 0;
            break;
        }
    }
    fclose(fp);
    return ret;
}

double calc_cpu_rate(cpu_info_t* old_info, cpu_info_t* new_info)
{
    double od, nd;
    double usr_dif, sys_dif, nice_dif;
    double user_cpu_rate;
    double kernel_cpu_rate;

    od = (double)(old_info->user + old_info->nice + old_info->system + old_info->idle + old_info->iowait + old_info->irq + old_info->softirq);
    nd = (double)(new_info->user + new_info->nice + new_info->system + new_info->idle + new_info->iowait + new_info->irq + new_info->softirq);

    if (nd - od) {
        user_cpu_rate = (new_info->user - old_info->user) / (nd - od) * 100;
        kernel_cpu_rate = (new_info->system - old_info->system) / (nd - od) * 100;
        return user_cpu_rate + kernel_cpu_rate;
    }
    return 0;
}

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
    int i=0;
    set_use_cpu(0);
    while(i<1000000) {
        for(int i=0;i<100;i++) {
            a+=1;
        }
        usleep(1);
        i++;
    }
    return NULL;
}

int main(int argc, char *argv[]) {
    pthread_t tid[100];
    cpu_info_t st,et;
    struct timeval start, end;
    int i, usec;
    int test_thread = atoi(argv[1]);
    set_use_cpu(1);
    get_cpu_occupy(0, &st);
    gettimeofday(&start, NULL);
    for(i=0;i<test_thread;i++){
        pthread_create(&tid[i], NULL, _test, NULL);
    }
    for(i=0;i<test_thread;i++) {
        pthread_join(tid[i], NULL);
    }
    gettimeofday(&end, NULL);
    usec = (1000000*(end.tv_sec-start.tv_sec)+ end.tv_usec-start.tv_usec);
    get_cpu_occupy(0, &et);
    printf("%d,%d,%.2f%%\n", test_thread, usec, calc_cpu_rate(&st, &et));
}
