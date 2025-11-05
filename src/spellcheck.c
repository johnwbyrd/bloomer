/*
 * C64 Bloom Filter Spell Checker
 *
 * Copyright (c) 2025 John Byrd
 * https://github.com/johnwbyrd/bloomer
 *
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * A spell checker for the Commodore 64 that uses a Bloom filter stored in a
 * REL file on disk. Words are hashed with 5 different hash functions and
 * checked against a bit array to determine if they exist in the dictionary.
 *
 * The Bloom filter provides:
 * - 0% false negatives (correct words always pass)
 * - ~0.81% false positives (some misspellings incorrectly pass)
 *
 * Compiled with LLVM-MOS for Commodore 64
 */

#include <c64.h>
#include <cbm.h>
#include <ctype.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "bloom_config.h"

/* ========================================================================== */
/* CONFIGURATION AND CONSTANTS                                               */
/* ========================================================================== */

#define MAX_WORD_LEN 64
#define RECORD_SIZE 254     /* CBM DOS REL max record size */
#define CBM_CMD_CHANNEL 15  /* CBM DOS command channel */
#define CBM_STATUS_EOF 0x40 /* End of file status bit */
#define BITS_PER_BYTE 8

/* PETSCII color control codes */
#define PETSCII_COLOR_GOOD 0x1E      /* Green text for correct words */
#define PETSCII_COLOR_BAD 0x1C       /* Red text for misspelled words */
#define PETSCII_COLOR_DEFAULT 0x9A   /* C64 default */

/* PETSCII symbols */
#define PETSCII_CIRCLE 0xCF   /* O symbol for OK */
#define PETSCII_X 0xD8        /* X symbol for NOT FOUND */

/* UI constants */
#define PROMPT_LENGTH 18   /* Length of "word (or 'quit'): " */
#define CHECKING_LENGTH 8  /* Length of "Checking" */

/* PETSCII character ranges */
#define PETSCII_LOWERCASE_START 0xC1
#define PETSCII_LOWERCASE_END 0xDA
#define PETSCII_UPPERCASE_START 0x41
#define PETSCII_UPPERCASE_END 0x5A
#define PETSCII_SHIFTED_START 0x61
#define PETSCII_SHIFTED_END 0x7A
#define PETSCII_TO_ASCII_OFFSET 0x80
#define LOWERCASE_TO_UPPERCASE_OFFSET 0x20

/* ========================================================================== */
/* TYPE DEFINITIONS                                                          */
/* ========================================================================== */

typedef uint32_t (*hash_func_t)(const char *, uint8_t);

/* ========================================================================== */
/* GLOBAL VARIABLES                                                          */
/* ========================================================================== */

/* Bloom filter file handles */
static uint8_t bloom_lfn = 2;
static uint8_t bloom_device = 8;
static uint8_t bloom_secondary = 2;

/* Buffer for reading REL records */
static uint8_t record_buffer[RECORD_SIZE];

/* Current loaded record number (-1 = none loaded) */
static int16_t current_record = -1;

/* Debug mode flag */
static bool debug_mode = false;

/* Progress indicator counter */
static uint8_t period_count = 0;

/* ========================================================================== */
/* HASH FUNCTIONS                                                            */
/* ========================================================================== */
/* Must match Python implementation exactly for compatibility                */

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

/* Array of hash functions - first NUM_HASH_FUNCTIONS will be used */
const hash_func_t hash_functions[NUM_HASH_FUNCTIONS] = {
    hash_fnv1a, hash_djb2, hash_sdbm, hash_jenkins, hash_murmur};

/* ========================================================================== */
/* CBM DOS UTILITIES                                                         */
/* ========================================================================== */
/* Low-level Commodore DOS error checking and status reading                 */

/*
 * Read DOS error status from command channel
 *
 * Returns: error code (0 = OK, 255 = communication error)
 *
 * If msg_buf is provided, the error message text is stored there.
 * Error messages are in format: "NN,MESSAGE,TT,SS" where NN is error code.
 */
static uint8_t read_dos_status(uint8_t device, char *msg_buf,
                               uint8_t msg_bufsize) {
  uint8_t err_code = 0;
  uint8_t idx = 0;
  uint8_t c, status;

  /* Set input to command channel */
  if (cbm_k_chkin(CBM_CMD_CHANNEL)) {
    cbm_k_clrch();
    if (msg_buf && msg_bufsize) {
      strncpy(msg_buf, "CHKIN 15 FAIL", msg_bufsize - 1);
      msg_buf[msg_bufsize - 1] = '\0';
    }
    return 255;
  }

  /* Read 2-digit error code */
  c = cbm_k_basin();
  if (c >= '0' && c <= '9')
    err_code = (c - '0') * 10;
  c = cbm_k_basin();
  if (c >= '0' && c <= '9')
    err_code += (c - '0');

  /* Read error message text if buffer provided */
  if (msg_buf && msg_bufsize > 0) {
    cbm_k_basin(); /* skip comma */
    while (idx < msg_bufsize - 1) {
      c = cbm_k_basin();
      status = cbm_k_readst();
      if (c == '\r' || (status & CBM_STATUS_EOF))
        break;
      msg_buf[idx++] = c;
    }
    msg_buf[idx] = '\0';
  }

  cbm_k_clrch();
  return err_code;
}

/*
 * Check DOS status after an operation
 *
 * Returns: true if OK (err_code 0 or in ok_codes list), false otherwise
 *
 * Reads the DOS error channel and optionally prints error messages.
 * Some operations return non-zero codes that aren't errors (e.g., file not
 * found when that's expected). Pass those codes in ok_codes array.
 */
static bool check_dos_status(uint8_t device, const char *operation,
                             const uint8_t *ok_codes, uint8_t num_ok_codes) {
  char msg[64];
  uint8_t err;
  uint8_t i;
  bool is_ok;

  err = read_dos_status(device, msg, sizeof(msg));

  if (debug_mode) {
    printf("%s: DOS %02u,%s\n", operation, err, msg);
  }

  /* Check if error code is 0 or in the OK list */
  is_ok = (err == 0);
  for (i = 0; i < num_ok_codes && !is_ok; i++) {
    if (err == ok_codes[i])
      is_ok = true;
  }

  if (!is_ok) {
    printf("ERR: %s failed\n", operation);
  }

  return is_ok;
}

/* ========================================================================== */
/* BLOOM FILTER FILE I/O                                                     */
/* ========================================================================== */
/* REL file management and bit-level access to Bloom filter data             */

/*
 * Open bloom filter file for reading
 *
 * Returns: true on success, false on error
 *
 * Opens BLOOM.DAT as a REL file with 254-byte records. The Bloom filter
 * data is stored sequentially across these records.
 */
static bool bloom_open(void) {
  uint8_t status;

  /* Open command channel */
  cbm_k_setlfs(CBM_CMD_CHANNEL, bloom_device, CBM_CMD_CHANNEL);
  cbm_k_setnam("");
  status = cbm_k_open();
  if (status) {
    printf("ERR: open cmd ch, status=%u\n", status);
    return false;
  }
  check_dos_status(bloom_device, "open cmd", NULL, 0);

  /* Open bloom data file as REL with RECORD_SIZE-byte records */
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

/*
 * Close bloom filter file
 */
static void bloom_close(void) {
  cbm_k_clrch();
  cbm_k_close(bloom_lfn);
  cbm_k_close(CBM_CMD_CHANNEL);
}

/*
 * Read one bit from bloom filter
 *
 * Returns: true if bit is set, false if bit is clear
 *
 * Translates bit position to record number and byte offset within record.
 * Caches the current record to avoid unnecessary disk seeks.
 */
static bool bloom_read_bit(uint32_t bit_pos) {
  uint32_t byte_off = bit_pos / BITS_PER_BYTE;
  uint8_t bit_off = bit_pos % BITS_PER_BYTE;
  uint16_t rec = byte_off / RECORD_SIZE;
  uint16_t byte_in_rec = byte_off % RECORD_SIZE;
  uint16_t dos_rec;
  uint16_t i;
  uint8_t st;

  /* Seek to record if not already cached */
  if (rec != current_record) {
    dos_rec = rec + 1; /* DOS record numbers are 1-based */

    /* Send POSITION command to command channel */
    st = cbm_k_chkout(CBM_CMD_CHANNEL);
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

    if (!debug_mode) {
      printf("."); /* Progress indicator */
      period_count++;
    }

    /* Read entire record into buffer */
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

  /* Check the bit in the cached record */
  return (record_buffer[byte_in_rec] & (1 << bit_off)) != 0;
}

/* ========================================================================== */
/* BLOOM FILTER LOGIC                                                        */
/* ========================================================================== */
/* High-level Bloom filter algorithm                                         */

/*
 * Check if word exists in Bloom filter
 *
 * Returns: true if word probably in dictionary (may have false positives)
 *          false if word definitely NOT in dictionary (no false negatives)
 *
 * Algorithm:
 * 1. Compute all hash values and their bit positions
 * 2. Sort bit positions for optimal disk access (left-to-right)
 * 3. Check each bit - return false immediately if any bit is unset
 * 4. Return true only if all bits are set
 */
static bool check_word(const char *word) {
  uint8_t i, j;
  uint32_t hash;
  uint32_t bit_positions[NUM_HASH_FUNCTIONS];
  uint32_t temp;

  /* Reset period counter */
  period_count = 0;

  if (!debug_mode) {
    printf("Checking");
  }

  /* Compute all bit positions using hash functions */
  for (i = 0; i < NUM_HASH_FUNCTIONS; i++) {
    hash = hash_functions[i](word, i);
    bit_positions[i] = hash % BLOOM_SIZE_BITS;
  }

  /* Sort bit positions to minimize disk seeks (bubble sort) */
  for (i = 0; i < NUM_HASH_FUNCTIONS - 1; i++) {
    for (j = 0; j < NUM_HASH_FUNCTIONS - 1 - i; j++) {
      if (bit_positions[j] < bit_positions[j + 1]) {
        temp = bit_positions[j];
        bit_positions[j] = bit_positions[j + 1];
        bit_positions[j + 1] = temp;
      }
    }
  }

  /* Check bits in sorted order (left-to-right on disk) */
  for (i = 0; i < NUM_HASH_FUNCTIONS; i++) {
    if (!bloom_read_bit(bit_positions[i])) {
      return false; /* Definitely not in dictionary */
    }
  }

  return true; /* Probably in dictionary */
}

/* ========================================================================== */
/* STRING UTILITIES                                                          */
/* ========================================================================== */
/* PETSCII conversion and string manipulation                                */

/*
 * Convert PETSCII input to uppercase ASCII
 *
 * Handles three PETSCII character ranges:
 * - PETSCII lowercase (0xC1-0xDA) -> ASCII uppercase (A-Z)
 * - PETSCII uppercase (0x41-0x5A) -> ASCII uppercase (A-Z)
 * - PETSCII shifted lowercase (0x61-0x7A) -> ASCII uppercase (A-Z)
 *
 * Conversion ensures consistent hashing regardless of how user typed the word.
 */
void petscii_to_ascii_upper(char *str) {
  while (*str) {
    unsigned char c = (unsigned char)*str;

    /* PETSCII lowercase letters (a-z) */
    if (c >= PETSCII_LOWERCASE_START && c <= PETSCII_LOWERCASE_END) {
      *str = c - PETSCII_TO_ASCII_OFFSET;
    }
    /* PETSCII uppercase letters (A-Z) - already ASCII */
    else if (c >= PETSCII_UPPERCASE_START && c <= PETSCII_UPPERCASE_END) {
      *str = c;
    }
    /* PETSCII shifted lowercase (A-Z) */
    else if (c >= PETSCII_SHIFTED_START && c <= PETSCII_SHIFTED_END) {
      *str = c - LOWERCASE_TO_UPPERCASE_OFFSET;
    }

    str++;
  }
}

/*
 * Trim leading and trailing whitespace
 */
void trim(char *str) {
  char *end;

  /* Trim leading space */
  while (isspace((unsigned char)*str))
    str++;

  if (*str == 0)
    return;

  /* Trim trailing space */
  end = str + strlen(str) - 1;
  while (end > str && isspace((unsigned char)*end))
    end--;

  *(end + 1) = '\0';
}

/* ========================================================================== */
/* MAIN PROGRAM                                                              */
/* ========================================================================== */

int main(void) {
  char word[MAX_WORD_LEN];
  bool result;
  uint8_t spaces_needed;
  uint8_t i;

  putchar(PETSCII_COLOR_DEFAULT);
  printf(DICT_INFO);

  /* Open bloom filter file */
  if (!bloom_open()) {
    printf("failed to open bloom.dat\n");
    return 1;
  }

  /* Main spell-checking loop */
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

    result = check_word(word);

    /* Calculate alignment: prompt length - "Checking" length - periods printed */
    spaces_needed = PROMPT_LENGTH - CHECKING_LENGTH - period_count;

    /* Print spaces to align under user's word */
    for (i = 0; i < spaces_needed; i++) {
      printf(" ");
    }

    /* Print colored result */
    if (result) {
      printf("%c%c %cOK\n", PETSCII_COLOR_GOOD, PETSCII_CIRCLE, PETSCII_COLOR_DEFAULT);
    } else {
      printf("%c%c %cNOT FOUND\n", PETSCII_COLOR_BAD, PETSCII_X, PETSCII_COLOR_DEFAULT);
    }
  }

  bloom_close();
  printf("\ngoodbye!\n");

  return 0;
}
