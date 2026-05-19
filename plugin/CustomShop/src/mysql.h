#pragma once
// ─────────────────────────────────────────────────────────────────
//  Minimal MySQL Connector/C (libmysql) API stub.
//
//  Provides enough declarations to compile the CustomShop plugin
//  without a full MySQL SDK installation.  At runtime the actual
//  implementations are loaded from libmysql.dll (MySQL Connector/C
//  8.x or MariaDB Connector/C — both are ABI-compatible here).
//
//  To BUILD the DLL you still need libmysql.lib (import library).
//  Download MySQL Connector/C 8.0 from:
//    https://dev.mysql.com/downloads/connector/c/
//  Copy libmysql.lib to  plugin/CustomShop/mysql/libmysql.lib
//  Copy libmysql.dll  to  plugin/CustomShop/bin/libmysql.dll
// ─────────────────────────────────────────────────────────────────

#ifndef MYSQL_H_STUB
#define MYSQL_H_STUB

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// ── Fundamental types ────────────────────────────────────────────

typedef unsigned char  my_bool;
typedef unsigned long long my_ulonglong;

// Opaque connection handle.  We only ever hold a pointer to it.
typedef struct st_mysql      MYSQL;

// Opaque result set handle.
typedef struct st_mysql_res  MYSQL_RES;

// A single row — array of (nullable) char* column values.
typedef char** MYSQL_ROW;

// ── Options enum ─────────────────────────────────────────────────

typedef enum enum_mysql_set_option {
    MYSQL_OPT_CONNECT_TIMEOUT  = 0,
    MYSQL_OPT_COMPRESS         = 1,
    MYSQL_OPT_NAMED_PIPE       = 2,
    MYSQL_INIT_COMMAND         = 3,
    MYSQL_READ_DEFAULT_FILE    = 4,
    MYSQL_READ_DEFAULT_GROUP   = 5,
    MYSQL_SET_CHARSET_DIR      = 6,
    MYSQL_SET_CHARSET_NAME     = 7,
    MYSQL_OPT_LOCAL_INFILE     = 8,
    MYSQL_OPT_PROTOCOL         = 9,
    MYSQL_SHARED_MEMORY_BASE_NAME = 10,
    MYSQL_OPT_READ_TIMEOUT     = 11,
    MYSQL_OPT_WRITE_TIMEOUT    = 12,
    MYSQL_OPT_USE_RESULT       = 13,
    MYSQL_SECURE_AUTH          = 20,
    MYSQL_REPORT_DATA_TRUNCATION = 21,
    MYSQL_OPT_RECONNECT        = 20,   // same numeric value as used by Connector/C 8
    MYSQL_OPT_SSL_MODE         = 55,
} enum_mysql_set_option;

// ── Client flags ─────────────────────────────────────────────────
#define CLIENT_LONG_PASSWORD     1
#define CLIENT_MULTI_STATEMENTS  (1UL << 16)
#define CLIENT_MULTI_RESULTS     (1UL << 17)

// ── Connection ───────────────────────────────────────────────────

MYSQL* __stdcall mysql_init(MYSQL* mysql);

MYSQL* __stdcall mysql_real_connect(
    MYSQL*       mysql,
    const char*  host,
    const char*  user,
    const char*  passwd,
    const char*  db,
    unsigned int port,
    const char*  unix_socket,
    unsigned long client_flag);

int __stdcall mysql_options(
    MYSQL*                    mysql,
    enum_mysql_set_option  option,
    const void*               arg);

int __stdcall mysql_set_character_set(MYSQL* mysql, const char* csname);

void __stdcall mysql_close(MYSQL* mysql);

// ── Queries ──────────────────────────────────────────────────────

int __stdcall mysql_query(MYSQL* mysql, const char* stmt_str);

int __stdcall mysql_real_query(
    MYSQL*        mysql,
    const char*   stmt_str,
    unsigned long length);

// ── Results ──────────────────────────────────────────────────────

MYSQL_RES* __stdcall mysql_store_result(MYSQL* mysql);

MYSQL_ROW  __stdcall mysql_fetch_row(MYSQL_RES* result);

void __stdcall mysql_free_result(MYSQL_RES* result);

my_ulonglong __stdcall mysql_num_rows(MYSQL_RES* result);

my_ulonglong __stdcall mysql_affected_rows(MYSQL* mysql);

// ── Errors ───────────────────────────────────────────────────────

const char*  __stdcall mysql_error(const MYSQL* mysql);
unsigned int __stdcall mysql_errno(MYSQL* mysql);

// ── Utility ──────────────────────────────────────────────────────

unsigned long __stdcall mysql_real_escape_string(
    MYSQL*        mysql,
    char*         to,
    const char*   from,
    unsigned long length);

#ifdef __cplusplus
} // extern "C"
#endif

#endif // MYSQL_H_STUB
