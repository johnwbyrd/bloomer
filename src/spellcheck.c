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
#define RECORD_SIZE 254  /* CBM DOS REL files support 1-254 byte records */

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

    /* Set up file parameters for REL file with 254-byte records */
    /* For REL files: third param is secondary address (2-14), record length goes in filename */
    cbm_k_setlfs(bloom_lfn, bloom_device, bloom_secondary);
    cbm_k_setnam("bloom.dat,l,\xFE");  /* \xFE = 254 = record length */

    /* Open the file */
    if (cbm_k_open()) {
        printf("error opening bloom.dat\n");
        return false;
    }

    /* Open command channel (leave it open for POSITION commands) */
    cbm_k_close(15);
    cbm_k_setlfs(15, bloom_device, 15);
    cbm_k_setnam("");
    if (cbm_k_open()) {
        printf("error opening command channel\n");
        cbm_k_close(bloom_lfn);
        return false;
    }

    current_record = -1;
    return true;
}

void close_bloom_file(void) {
    cbm_k_clrch();
    cbm_k_close(15);  /* Close command channel */
    cbm_k_close(bloom_lfn);
    current_record = -1;
}

bool seek_to_record(uint16_t record_num) {
    char cmd[32];
    uint8_t cmd_len;

    if (record_num == current_record) {
        return true;  /* Already positioned */
    }

    /* Use POSITION command for REL file random access */
    /* Format: "P" + channel + record_low + record_high + byte_in_record */
    /* Record numbers are 1-based in CBM DOS, so add 1 */
    uint16_t dos_record = record_num + 1;

    /* Send POSITION command: P{channel},{record_low},{record_high},{position} */
    /* Channel number is 96 + secondary address (e.g., 96+2=98 for channel 2) */
    cmd_len = sprintf(cmd, "P%c%c%c%c",
                      (char)(96 + bloom_secondary),
                      (char)(dos_record & 0xFF),
                      (char)((dos_record >> 8) & 0xFF),
                      (char)1);  /* Position to byte 1 (first data byte) */

    printf("seek rec %u: P/%u/%u/%u/1\n", record_num,
           (unsigned)(96 + bloom_secondary),
           (unsigned)(dos_record & 0xFF),
           (unsigned)((dos_record >> 8) & 0xFF));

    /* Set output to command channel */
    if (cbm_k_chkout(15)) {
        return false;
    }

    /* Send command */
    for (uint8_t i = 0; i < cmd_len; i++) {
        cbm_k_bsout(cmd[i]);
    }

    /* Clear channel after sending command */
    cbm_k_clrch();

    current_record = record_num;
    return true;
}

bool read_current_record(void) {
    uint16_t i;

    /* Ensure input channel is set to bloom file */
    if (cbm_k_chkin(bloom_lfn)) {
        printf("error setting input channel\n");
        return false;
    }

    printf("reading rec %d... ", current_record);

    for (i = 0; i < RECORD_SIZE; i++) {
        record_buffer[i] = cbm_k_basin();
        if (cbm_k_readst()) {
            printf("read error at byte %u\n", i);
            return false;
        }
    }

    printf("ok [%02x %02x %02x %02x]\n",
           record_buffer[0], record_buffer[1],
           record_buffer[2], record_buffer[3]);

    return true;
}

bool check_bit(uint32_t bit_position) {
    uint32_t byte_offset = bit_position / 8;
    uint8_t bit_offset = bit_position % 8;
    uint16_t record_num = byte_offset / RECORD_SIZE;
    uint16_t byte_in_record = byte_offset % RECORD_SIZE;
    bool bit_set;

    printf("  bit %lu: byte %lu = rec %u + %u, bit %u\n",
           (unsigned long)bit_position,
           (unsigned long)byte_offset,
           (unsigned)record_num,
           (unsigned)byte_in_record,
           (unsigned)bit_offset);

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
    bit_set = (record_buffer[byte_in_record] & (1 << bit_offset)) != 0;
    printf("  -> byte[%u]=0x%02x, bit %u = %d\n",
           (unsigned)byte_in_record,
           record_buffer[byte_in_record],
           (unsigned)bit_offset,
           bit_set ? 1 : 0);

    return bit_set;
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

void petscii_to_ascii_upper(char *str) {
    /* Convert PETSCII input to uppercase ASCII for consistent hashing
     * PETSCII lowercase (0xC1-0xDA) -> ASCII uppercase (0x41-0x5A)
     * PETSCII uppercase (0x41-0x5A) -> ASCII uppercase (0x41-0x5A)
     */
    while (*str) {
        unsigned char c = (unsigned char)*str;

        /* PETSCII lowercase letters (a-z: 0xC1-0xDA) */
        if (c >= 0xC1 && c <= 0xDA) {
            *str = c - 0x80;  /* Convert to ASCII uppercase A-Z */
        }
        /* PETSCII uppercase letters (A-Z: 0x41-0x5A) - already ASCII */
        else if (c >= 0x41 && c <= 0x5A) {
            *str = c;  /* Already uppercase ASCII */
        }
        /* PETSCII shifted lowercase (A-Z: 0x61-0x7A) */
        else if (c >= 0x61 && c <= 0x7A) {
            *str = c - 0x20;  /* Convert to uppercase */
        }

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
        cbm_k_clrch();  /* Clear channel to restore keyboard input */
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

        /* Convert PETSCII to uppercase ASCII */
        petscii_to_ascii_upper(word);

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
