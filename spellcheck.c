/*
 * C64 Spell Checker using Bloom Filter
 * Compiled with LLVM-MOS for Commodore 64
 */

#include <stdio.h>
#include <string.h>
#include <ctype.h>
#include <stdbool.h>
#include <stdint.h>
#include <c64.h>
#include <cbm.h>

#include "bloom_config.h"

#define MAX_WORD_LEN 64
#define RECORD_SIZE 256

/* File handle for Bloom filter */
static uint8_t bloom_lfn = 2;
static uint8_t bloom_device = 8;
static uint8_t bloom_secondary = 2;

/* Buffer for reading records */
static uint8_t record_buffer[RECORD_SIZE];

/* Current loaded record number (-1 = none) */
static int16_t current_record = -1;


/*
 * Hash functions - must match Python implementation exactly
 */

uint32_t hash_fnv1a(const char *word, uint8_t seed) {
    uint32_t hash = 2166136261UL + seed;
    while (*word) {
        hash ^= (uint8_t)(*word);
        hash *= 16777619UL;
        word++;
    }
    return hash;
}

uint32_t hash_djb2(const char *word, uint8_t seed) {
    uint32_t hash = 5381UL + seed;
    while (*word) {
        hash = ((hash << 5) + hash) + (uint8_t)(*word);
        word++;
    }
    return hash;
}

uint32_t hash_sdbm(const char *word, uint8_t seed) {
    uint32_t hash = seed;
    while (*word) {
        hash = (uint8_t)(*word) + (hash << 6) + (hash << 16) - hash;
        word++;
    }
    return hash;
}

uint32_t hash_jenkins(const char *word, uint8_t seed) {
    uint32_t hash = seed;
    while (*word) {
        hash += (uint8_t)(*word);
        hash += (hash << 10);
        hash ^= (hash >> 6);
        word++;
    }
    hash += (hash << 3);
    hash ^= (hash >> 11);
    hash += (hash << 15);
    return hash;
}

uint32_t hash_murmur(const char *word, uint8_t seed) {
    uint32_t hash = seed + 0x9747b28cUL;
    while (*word) {
        hash ^= (uint8_t)(*word);
        hash *= 0x5bd1e995UL;
        hash ^= (hash >> 15);
        word++;
    }
    return hash;
}

typedef uint32_t (*hash_func_t)(const char *, uint8_t);

const hash_func_t hash_functions[NUM_HASH_FUNCTIONS] = {
    hash_fnv1a,
    hash_djb2,
    hash_sdbm,
    hash_jenkins,
    hash_murmur
};


/*
 * Disk I/O functions
 */

bool open_bloom_file(void) {
    cbm_k_close(bloom_lfn);

    /* Set up file parameters */
    cbm_k_setlfs(bloom_lfn, bloom_device, bloom_secondary);
    cbm_k_setnam("bloom.dat,s,r");

    /* Open the file */
    if (cbm_k_open()) {
        printf("error opening bloom.dat\n");
        return false;
    }

    /* Set input channel */
    if (cbm_k_chkin(bloom_lfn)) {
        printf("error setting input channel\n");
        cbm_k_close(bloom_lfn);
        return false;
    }

    current_record = -1;
    return true;
}

void close_bloom_file(void) {
    cbm_k_clrch();
    cbm_k_close(bloom_lfn);
    current_record = -1;
}

bool seek_to_record(uint16_t record_num) {
    uint32_t byte_offset;
    uint32_t i;

    if (record_num == current_record) {
        return true;  /* Already positioned */
    }

    /* Close and reopen to reset position */
    close_bloom_file();
    if (!open_bloom_file()) {
        return false;
    }

    /* Seek by reading bytes (no POSITION command available for SEQ) */
    byte_offset = (uint32_t)record_num * RECORD_SIZE;

    for (i = 0; i < byte_offset; i++) {
        cbm_k_basin();
        if (cbm_k_readst()) {
            printf("seek error\n");
            return false;
        }
    }

    current_record = record_num;
    return true;
}

bool read_current_record(void) {
    uint16_t i;

    for (i = 0; i < RECORD_SIZE; i++) {
        record_buffer[i] = cbm_k_basin();
        if (cbm_k_readst()) {
            printf("read error\n");
            return false;
        }
    }

    return true;
}

bool check_bit(uint32_t bit_position) {
    uint32_t byte_offset = bit_position / 8;
    uint8_t bit_offset = bit_position % 8;
    uint16_t record_num = byte_offset / RECORD_SIZE;
    uint16_t byte_in_record = byte_offset % RECORD_SIZE;
    
    /* Seek to the correct record if needed */
    if (record_num != current_record) {
        if (!seek_to_record(record_num)) {
            return false;
        }
        
        if (!read_current_record()) {
            return false;
        }
    }
    
    /* Check the bit */
    return (record_buffer[byte_in_record] & (1 << bit_offset)) != 0;
}


/*
 * Bloom filter check
 */

bool check_word(const char *word) {
    uint8_t i;
    uint32_t hash_val;
    uint32_t bit_pos;
    
    /* Check all hash functions */
    for (i = 0; i < NUM_HASH_FUNCTIONS; i++) {
        hash_val = hash_functions[i](word, i);
        bit_pos = hash_val % BLOOM_SIZE_BITS;
        
        if (!check_bit(bit_pos)) {
            return false;  /* Definitely not in set */
        }
    }
    
    return true;  /* Probably in set */
}


/*
 * String utilities
 */

void to_upper(char *str) {
    while (*str) {
        *str = toupper((unsigned char)*str);
        str++;
    }
}

void trim(char *str) {
    char *end;
    
    /* Trim leading space */
    while (isspace((unsigned char)*str)) str++;
    
    if (*str == 0) return;
    
    /* Trim trailing space */
    end = str + strlen(str) - 1;
    while (end > str && isspace((unsigned char)*end)) end--;
    
    *(end + 1) = '\0';
}


/*
 * Main program
 */

int main(void) {
    char word[MAX_WORD_LEN];
    bool result;

    printf("c64 bloom filter spell checker\n");
    printf("================================\n\n");
    printf("loading bloom filter...\n");
    
    /* Open Bloom filter file */
    if (!open_bloom_file()) {
        printf("\nfailed to open bloom.dat\n");
        return 1;
    }
    
    printf("ready!\n\n");
    
    /* Main loop */
    while (1) {
        printf("enter word (or 'quit'): ");
        
        /* Read line */
        if (fgets(word, sizeof(word), stdin) == NULL) {
            break;
        }
        
        /* Remove newline and trim */
        trim(word);
        
        if (strlen(word) == 0) {
            continue;
        }
        
        /* Convert to uppercase */
        to_upper(word);
        
        /* Check for quit */
        if (strcmp(word, "QUIT") == 0) {
            break;
        }
        
        /* Check spelling */
        printf("checking '%s'...\n", word);
        result = check_word(word);
        
        if (result) {
            printf("  -> probably correct\n\n");
        } else {
            printf("  -> not found\n\n");
        }
    }
    
    /* Cleanup */
    close_bloom_file();
    
    printf("\ngoodbye!\n");
    
    return 0;
}
