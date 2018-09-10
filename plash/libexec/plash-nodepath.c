#include <sys/types.h>
#include <sys/stat.h>
#include <linux/limits.h>
#include <unistd.h>
#include <stdio.h>
#include <errno.h>

// #undef PATH_MAX
//#define PATH_MAX 4
#define DATA_INDEX "/home/resu/"

int main(int argc, char *argv[]){
    //if (argc != 1) { // not working
       //printf("missing argument");
    //}

    char linkName[sizeof(argv[1])];
    snprintf(linkName, 100, "/home/ihucos/.plashdata/index/%s", argv[1]);
    // printf("%s", linkName);
    // return 1;

    char link[PATH_MAX + 1];
    struct stat sb;

    int nbytes = readlink(linkName, link, PATH_MAX + 1);
    if (nbytes == -1) {
        if (errno ==  ENOENT){
            fprintf(stderr, "no such container %s\n", argv[1]);
            return 3;
        }
        perror("readlink");
        return 1;
    } else if (nbytes == PATH_MAX + 1) {
        fprintf(stderr, "path too long\n");
        return 1;
    }
    if (stat(link, &sb) == -1){
        if (errno ==  ENOENT){
            fprintf(stderr, "no such container %s\n", argv[1]);
            return 3;
        }
        perror("stat");
        return 1;
    }

    printf("%s\n", link);
    return 0;
}
