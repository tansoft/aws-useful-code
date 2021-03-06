#define _GNU_SOURCE
#define __USE_GNU
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/time.h>
#include <pthread.h>
#include <sched.h>

// you can choose to use the CPU utilization of system or the CPU utilization of process for statistics
// We recommend using the process CPU utilization, because the system utilization is regularly sampled, and statistics will be lost during frequent thread switching
// https://lrita.github.io/images/posts/linux/Linux_CPU_Usage_Analysis.pdf
//#define USE_SYSTEM_CPU_STAT

// Each thread can be bind with a vCPU separately, which can disable the affinity considered by vCPU during thread switching
//#define BIND_SINGLE_VCPU_PRE_THREAD

//Total sampling times
#define TEST_COUNT 50
//Number of test cycles per test
#define TEST_PRE_COUNT 10000
//Vcpu index to start using, start from index 0
#define START_CPU_INDEX 0
//max test vCPUs
#define MAX_CPU 64
//Pipeline for reporting data
int pipes[2];
//Number of test threads
int test_thread = 0;
//Number of test vCPUs
int use_cpu = 1;
//Use test method
int use_method = 0;

#ifdef __aarch64__
    #define SYS "aarch64"
#elif defined(__x86_64__)
    #define SYS "x86_64"
#else
    #define SYS "unknown"
#endif

#ifdef USE_SYSTEM_CPU_STAT
    #ifdef BIND_SINGLE_VCPU_PRE_THREAD
        #define STAT "cpustatbind"
    #else
        #define STAT "cpustat"
    #endif
#else
    #ifdef BIND_SINGLE_VCPU_PRE_THREAD
        #define STAT "prostatbind"
    #else
        #define STAT "prostat"
    #endif
#endif

#ifdef USE_SYSTEM_CPU_STAT

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

//Get the CPU stat
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

//Calculate CPU utilization
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

#else

typedef struct _process_info
{
    unsigned int pid;
    char name[40];
    char state;
    unsigned int ppid;
    unsigned int pgrp;
    unsigned int session;
    unsigned int tty_nr;
    unsigned int tpgid;
    unsigned int flags;

    unsigned long minflt;
    unsigned long cminflt;
    unsigned long majflt;
    unsigned long cmajflt;

    unsigned long utime;
    unsigned long stime;
    unsigned long cutime;
    unsigned long cstime;

    unsigned long priority;
    unsigned long nice;
    unsigned long num_threads;
    unsigned long itrealvalue;
    unsigned long starttime;
}process_info_t;

//Get the process stat
int get_process_occupy(process_info_t* info)
{
    FILE* fp = NULL;
    char key[20] = {0};
    char buf[1024] = {0};
    sprintf(key, "/proc/%u/stat", (unsigned int)getpid());
    fp = fopen(key, "r");
    if (fgets(buf, sizeof(buf), fp)) {
        sscanf(buf, "%u %s %c %u %u %u %u %u %u %lu %lu %lu %lu %lu %lu %lu %lu %lu %lu %lu %lu %lu", &info->pid, info->name, &info->state,
               &info->ppid, &info->pgrp, &info->session, &info->tty_nr, &info->tpgid, &info->flags,
               &info->minflt, &info->cminflt, &info->majflt, &info->cmajflt,
               &info->utime, &info->stime, &info->cutime, &info->cstime,
               &info->priority, &info->nice, &info->num_threads, &info->itrealvalue, &info->starttime);
        //printf("%u %u %u %u %u %u %lu %lu %lu %lu %lu %lu %lu %lu\n", info->ppid, info->pgrp, info->session, info->tty_nr, info->tpgid, info->flags,
        //      info->minflt, info->cminflt, info->majflt, info->cmajflt,
        //      info->utime,info->stime,info->cutime,info->cstime);
    } else {
      fclose(fp);
      return 0;
    }
    fclose(fp);
    return info->utime + info->stime + info->cutime + info->cstime;
}

#endif

//Set which vCPU used by the thread. start: is the index of the begin range of vCPU, start form 0. count: is the number of vCPUs used continuously
//e.g. set_use_cpu(2, 3) => use vCPU2 vCPU3 vCPU4 together
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
    static double a=0;
    for(int i=0;i<TEST_PRE_COUNT;i++) {
        a+=1;
        //usleep can cause thread switching
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
#ifdef BIND_SINGLE_VCPU_PRE_THREAD
    //Each thread is bound to a fixed vCPU separately
    set_use_cpu((START_CPU_INDEX+i) % use_cpu, 1);
#else
    //Fixed use 'use_cpu' CPUs starting with START_CPU_INDEX
    set_use_cpu(START_CPU_INDEX, use_cpu);
#endif
    while(1) {
        gettimeofday(&start, NULL);
        methods[use_method]();
        gettimeofday(&end, NULL);
        usec = (1000000*(end.tv_sec-start.tv_sec)+ end.tv_usec-start.tv_usec);
        //Send the execution time to the main thread for statistics
        if(write(pipes[1],&usec,sizeof(int))==-1) exit(1);
    }
    return NULL;
}

int main(int argc, char *argv[]) {
    int i,usec;
    long sum = 0;
    long count = 0;
    pthread_t tid;
    double cpurate;
    int cpucount;
#ifdef USE_SYSTEM_CPU_STAT
    cpu_info_t sinfo[MAX_CPU];
    cpu_info_t einfo[MAX_CPU];
#else
    process_info_t info;
    long stime,etime;
    double sectick;
    struct timeval start, end;
    int clock_ticks;
#endif

    if (argc < 2) {
        printf("usage: threadtest <thread_count> <use_cpu> <use_method>\n");
        return 1;
    }
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
    printf("method %s-%s-%d-%s: test %d cpus with %d threads\n", SYS, STAT, use_method, method_name[use_method], use_cpu, test_thread);

    if(pipe(pipes)<0) {
        exit(1);
    }

    //init threads
    for(i=0;i<test_thread;i++){
        pthread_create(&tid, NULL, _test, (void *)(long)i);
    }
    //sleep for 500ms to make the thread run stably
    usleep(500000);
    //The main thread uses the last CPU to avoid affecting the test in thread
    set_use_cpu(cpucount-1, 1);

#ifdef USE_SYSTEM_CPU_STAT
    for(i=0;i<use_cpu;i++) {
        get_cpu_occupy(START_CPU_INDEX+i, &sinfo[i]);
    }
#else
    clock_ticks = sysconf(_SC_CLK_TCK);
    gettimeofday(&start, NULL);
    stime = get_process_occupy(&info);
#endif

    while(count<TEST_COUNT) {
        //Get the time-consuming results sent by each thread
        for(i=0;i<test_thread;i++) {
            read(pipes[0],&usec,sizeof(int));
            sum+=usec;
        }
        count++;
#ifdef USE_SYSTEM_CPU_STAT
        cpurate = 0.0;
        for(i=0;i<use_cpu;i++) {
            get_cpu_occupy(START_CPU_INDEX+i, &einfo[i]);
            cpurate += calc_cpu_rate(&sinfo[i], &einfo[i]);
        }
        cpurate /= use_cpu;
#else
        gettimeofday(&end, NULL);
        etime = get_process_occupy(&info);
        sectick = (end.tv_sec-start.tv_sec)+(end.tv_usec-start.tv_usec)/1000000.0;
        cpurate = (etime - stime)*100.0/(sectick * clock_ticks);
#endif
        printf("threads: %d times: %d speed: %6.2fus cpu:%6.2f%%\n",
                test_thread, count,
                sum*1.0/count/test_thread,
                cpurate);
    }
    //printing average use time and average CPU utilization
    printf("mode-%s-%s-%d-%s-%d,%d,%.2f,%.2f\n",
        SYS, STAT, use_method, method_name[use_method], use_cpu, test_thread,
        sum*1.0/count/test_thread, cpurate);
    close(pipes[0]);
    close(pipes[1]);
}
