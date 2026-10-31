---
name: secure-secret
description: Ask the user for an API key via a masked prompt.
version: 1.0.0
author: Zach Vorhies, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [secret, credential, api-key, token, password, env, setup]
    category: security
    secret_request: true
---

# Secure Secret Skill

Collects a credential (API key, token, password) from the user through a masked prompt and saves it
to the profile `.env`. The value never enters the conversation: you only learn whether it was saved.

## When to Use

- A task needs a credential that is not set (a tool or script reports a missing `$SOME_API_KEY`).
- The user offers to give you a key or token: use this instead of letting them paste it in chat.

## Prerequisites

An interactive surface (desktop app, TUI, local CLI). Messaging platforms cannot show a masked
prompt; there the result carries `gateway_setup_hint` telling the user to edit `.env` themselves.

## How to Run

Call `skill_view` with `name="secure-secret"` and `file_path="request/<ENV_VAR_NAME>"`, for example
`skill_view(name="secure-secret", file_path="request/OPENWEATHER_API_KEY")`.

## Quick Reference

| Result field | Meaning |
|---|---|
| `stored: true` | Saved to `.env`; `$ENV_VAR_NAME` is available to tools now. |
| `stored: false`, `setup_skipped: true` | The user dismissed the prompt. |
| `gateway_setup_hint` | No masked prompt on this surface; relay the hint. |

## Procedure

1. Pick the exact env var name the consuming tool or script reads.
2. Tell the user in one line what the key is for and where to get it.
3. Call `skill_view` as above and wait for the result.
4. On `stored: true`, continue the task. Otherwise explain what is missing and stop.

## Pitfalls

- Never ask the user to paste a secret into chat, and never echo, log or write it to a file yourself.
- One variable per call. Do not retry a skipped prompt without the user asking.

## Verification

The result says `stored: true`; `terminal` commands see `$ENV_VAR_NAME` set (do not print it).
