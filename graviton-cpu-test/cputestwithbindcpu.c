#define _GNU_SOURCE
#define __USE_GNU
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/time.h>
#include <pthread.h>
#include <sched.h>

//总共循环次数
#define TEST_COUNT 50
//每次测试循环次数
#define TEST_PRE_COUNT 10000
//开始使用的核索引，从0开始
#define START_CPU_INDEX 0
//最多测试的cpu核数
#define MAX_CPU 64
//用于上报数据的管道
int pipes[2];
//测试线程数
int test_thread = 0;
//使用cpu核数
int use_cpu = 1;
//使用的测试方法
int use_method = 0;

#ifdef __aarch64__
    #define SYS "aarch64"
#elif defined(__x86_64__)
    #define SYS "x86_64"
#else
    #define SYS "unknown"
#endif

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

//获取某个cpu的负载
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

//计算cpu的使用率
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

//设置该线程使用哪个cpu，start是起始cpu索引，从0开始，count是连续使用多少个cpu
void set_use_cpu(int start, int count) {
    cpu_set_t cpuset;
    pthread_t tid = pthread_self();
    CPU_ZERO(&cpuset);
    for(int i=0; i<count; i++) {
        CPU_SET(i + start, &cpuset);
    }
    if (pthread_setaffinity_np(tid, sizeof(cpu_set_t), &cpuset) != 0) {
        printf("set addinity error\n");
        exit(1);
    }
}

void method0_inc() {
    static int a=0;
    for(int i=0;i<TEST_PRE_COUNT;i++) {
        a+=1;
        //sleep可以引起线程切换
        usleep(1);
    }
}

void method1_memcpy() {
    static char membuf[TEST_PRE_COUNT] = {0};
    char distbuf[TEST_PRE_COUNT];
    for(int i=0;i<TEST_PRE_COUNT;i++) {
        memcpy(distbuf, membuf+i, TEST_PRE_COUNT-i);
    }
}

typedef void (*method_function)();
method_function methods[] = {method0_inc, method1_memcpy};
char method_name[][10] = {"inc", "memcpy"};

void *_test(void *arg) {
    int usec;
    int i=(int)(long)arg;
    struct timeval start, end;
    //固定使用index开始的n个cpu
    set_use_cpu(i, 1);
    while(1) {
        gettimeofday(&start, NULL);
        methods[use_method]();
        gettimeofday(&end, NULL);
        usec = (1000000*(end.tv_sec-start.tv_sec)+ end.tv_usec-start.tv_usec);
        if(write(pipes[1],&usec,sizeof(int))==-1) exit(1);
    }
    return NULL;
}

int main(int argc, char *argv[]) {
    int i,usec;
    long sum = 0;
    long count = 0;
    pthread_t tid;
    cpu_info_t sinfo[MAX_CPU];
    cpu_info_t einfo[MAX_CPU];
    double cpurate;
    int cpucount;

    test_thread = atoi(argv[1]);
    if (test_thread < 1) {
        printf("The value of thread_count should be greater than 2\n");
        return 1;
    }
    cpucount = sysconf(_SC_NPROCESSORS_ONLN);
    if (argc > 2) {
        use_cpu = atoi(argv[2]);
        if (use_cpu < 1 || use_cpu > MAX_CPU) {
            printf("The value of use_cpu should be between 1 - %d\n", MAX_CPU);
            return 1;
        }
        if (use_cpu > cpucount) {
            printf("This system has only %d CPUs, use_cpu setting must be less than or equal to this value\n", cpucount);
            return 1;
        }
        if (argc > 3) {
            int method_count = sizeof(methods)/sizeof(method_function);
            use_method = atoi(argv[3]);
            if (use_method < 0 || use_method >= method_count) {
                printf("The value of use_method should be between 0 - %d\n", method_count-1);
                return 1;
            }
        }
    }
    printf("method %d-%s: test %d cpus with %d threads\n", use_method, method_name[use_method], use_cpu, test_thread);

    if(pipe(pipes)<0) {
        exit(1);
    }

    //init
    for(i=0;i<test_thread;i++){
        pthread_create(&tid, NULL, _test, (void *)(long)(i%use_cpu));
    }
    usleep(500000);
    //主线程指定为最后一个cpu
    set_use_cpu(cpucount-1, 1);

    for(i=0;i<use_cpu;i++) {
        get_cpu_occupy(START_CPU_INDEX+i, &sinfo[i]);
    }
    while(count<TEST_COUNT) {
        for(i=0;i<test_thread;i++) {
            read(pipes[0],&usec,sizeof(int));
            sum+=usec;
        }
        count++;
        cpurate = 0.0;
        for(i=0;i<use_cpu;i++) {
            get_cpu_occupy(START_CPU_INDEX+i, &einfo[i]);
            cpurate += calc_cpu_rate(&sinfo[i], &einfo[i]);
        }
        cpurate /= use_cpu;
        printf("threads: %d times: %d speed: %6.2fus cpu:%6.2f%%\n",
                test_thread, count,
                sum*1.0/count/test_thread,
                cpurate);
    }
    printf("mode-%s-%d-%s-%d,%d,%.2f,%.2f\n",
        SYS, use_method, method_name[use_method], use_cpu, test_thread,
        sum*1.0/count/test_thread, cpurate);
    close(pipes[0]);
    close(pipes[1]);
}
