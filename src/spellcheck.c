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
 * Disk I/O Error Checking - called after EVERY disk operation
 */

/* Read DOS error status from command channel 15
 * Returns: error code (0 = OK)
 */
static uint8_t read_dos_status(uint8_t device, char *msg_buf, uint8_t msg_bufsize) {
    uint8_t err_code = 0;
    uint8_t idx = 0;
    uint8_t c, status;

    /* Set input to command channel */
    if (cbm_k_chkin(15)) {
        cbm_k_clrch();
        if (msg_buf && msg_bufsize) {
            strncpy(msg_buf, "CHKIN 15 FAIL", msg_bufsize - 1);
            msg_buf[msg_bufsize - 1] = '\0';
        }
        return 255;
    }

    /* Read 2-digit error code */
    c = cbm_k_basin();
    if (c >= '0' && c <= '9') err_code = (c - '0') * 10;
    c = cbm_k_basin();
    if (c >= '0' && c <= '9') err_code += (c - '0');

    /* Read error message text if buffer provided */
    if (msg_buf && msg_bufsize > 0) {
        cbm_k_basin();  /* skip comma */
        while (idx < msg_bufsize - 1) {
            c = cbm_k_basin();
            status = cbm_k_readst();
            if (c == '\r' || (status & 0x40)) break;  /* CR or EOF */
            msg_buf[idx++] = c;
        }
        msg_buf[idx] = '\0';
    }

    cbm_k_clrch();
    return err_code;
}

/* Print and check DOS status after an operation
 * Returns: true if OK (err_code 0 or in ok_codes list), false otherwise
 */
static bool check_dos_status(uint8_t device, const char *operation, const uint8_t *ok_codes, uint8_t num_ok_codes) {
    char msg[64];
    uint8_t err;
    uint8_t i;
    bool is_ok;

    err = read_dos_status(device, msg, sizeof(msg));

    printf("%s: DOS %02u,%s\n", operation, err, msg);

    /* Check if error code is 0 or in the OK list */
    is_ok = (err == 0);
    for (i = 0; i < num_ok_codes && !is_ok; i++) {
        if (err == ok_codes[i]) is_ok = true;
    }

    if (!is_ok) {
        printf("ERR: %s failed\n", operation);
    }

    return is_ok;
}


/*
 * Disk I/O functions
 */

/* Open bloom filter for reading
 * Returns: true on success, false on error
 */
static bool bloom_open(void) {
    uint8_t status;

    /* Open command channel */
    cbm_k_setlfs(15, bloom_device, 15);
    cbm_k_setnam("");
    status = cbm_k_open();
    if (status) {
        printf("ERR: open cmd ch, status=%u\n", status);
        return false;
    }
    check_dos_status(bloom_device, "open cmd", NULL, 0);

    /* Open bloom data file as REL with 254-byte records */
    cbm_k_setlfs(bloom_lfn, bloom_device, bloom_secondary);
    cbm_k_setnam("BLOOM.DAT,L,\xFE");
    status = cbm_k_open();
    if (status) {
        printf("ERR: open bloom, status=%u\n", status);
        return false;
    }
    if (!check_dos_status(bloom_device, "open bloom", NULL, 0)) {
        return false;
    }

    current_record = -1;
    return true;
}

/* Close bloom filter */
static void bloom_close(void) {
    cbm_k_clrch();
    cbm_k_close(bloom_lfn);
    cbm_k_close(15);
}

/* Read one bit from bloom filter
 * Returns: true if bit set, false if bit clear
 */
static bool bloom_read_bit(uint32_t bit_pos) {
    uint32_t byte_off = bit_pos / 8;
    uint8_t bit_off = bit_pos % 8;
    uint16_t rec = byte_off / RECORD_SIZE;
    uint16_t byte_in_rec = byte_off % RECORD_SIZE;
    uint16_t dos_rec;
    uint16_t i;
    uint8_t st;

    /* Seek to record if needed */
    if (rec != current_record) {
        dos_rec = rec + 1;  /* 1-based */

        /* Send POSITION command */
        st = cbm_k_chkout(15);
        if (st) {
            cbm_k_clrch();
            printf("ERR: chkout 15=%u\n", st);
            return false;
        }

        cbm_k_bsout('P');
        cbm_k_bsout(bloom_secondary);
        cbm_k_bsout(dos_rec & 0xFF);
        cbm_k_bsout((dos_rec >> 8) & 0xFF);
        cbm_k_bsout(1);

        cbm_k_clrch();
        check_dos_status(bloom_device, "position", NULL, 0);

        /* Read record */
        st = cbm_k_chkin(bloom_lfn);
        if (st) {
            cbm_k_clrch();
            printf("ERR: chkin %u=%u\n", bloom_lfn, st);
            return false;
        }

        for (i = 0; i < RECORD_SIZE; i++) {
            record_buffer[i] = cbm_k_basin();
        }

        cbm_k_clrch();
        current_record = rec;
    }

    return (record_buffer[byte_in_rec] & (1 << bit_off)) != 0;
}


/*
 * Bloom filter check
 */

static bool check_word(const char *word) {
    uint8_t i;
    uint32_t hash;
    uint32_t bit_pos;

    for (i = 0; i < NUM_HASH_FUNCTIONS; i++) {
        hash = hash_functions[i](word, i);
        bit_pos = hash % BLOOM_SIZE_BITS;

        if (!bloom_read_bit(bit_pos)) {
            return false;  /* Definitely not in dictionary */
        }
    }

    return true;  /* Probably in dictionary */
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

    printf("c64 bloom filter spell checker\n");
    printf("================================\n\n");

    /* Open bloom filter */
    if (!bloom_open()) {
        printf("failed to open bloom.dat\n");
        return 1;
    }

    printf("ready!\n\n");

    /* Main loop */
    while (1) {
        cbm_k_clrch();
        printf("word (or 'quit'): ");

        if (fgets(word, sizeof(word), stdin) == NULL) {
            break;
        }

        trim(word);
        if (strlen(word) == 0) {
            continue;
        }

        petscii_to_ascii_upper(word);

        if (strcmp(word, "QUIT") == 0) {
            break;
        }

        if (check_word(word)) {
            printf("  OK\n");
        } else {
            printf("  NOT FOUND\n");
        }
    }

    bloom_close();
    printf("\ngoodbye!\n");

    return 0;
}
