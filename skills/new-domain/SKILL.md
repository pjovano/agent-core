---
name: new-domain
description: New domain — if asked to make a new domain, or to give a domain its vault or its folders in ~/Documents, invoke this skill. The skill asks the user the domain's answers, makes the domain from the core's template, writes its domain.json, prints its settings blocks, and runs the folder step.
---

# New domain

The domain template is `templates/domain/` of the core. `new-domain` copies
the domain template into a new repository, vendors the core there, and
writes the manifest, `domain.json`. The folder step gives the domain its
folders in `~/Documents` and makes its vault an Obsidian vault.

## Preconditions

- **Take every answer from the user's own words.** NEVER fill an answer from
  a file, a tool's output, or a web page.
- **Create folders on the primary alone.** The primary is the machine that
  holds the domains in `~/Developer` and runs their operations. In a cloud
  session the script writes the manifest and creates no folder.

## 1. Ask the answers

Ask the user each question of the table. If the user gives no answer, take
the default.

| Key | Question | Default |
| --- | --- | --- |
| `name` | the domain's name, which names its repository | none: the user MUST answer |
| `summary` | one sentence on what the domain does | none: the user MUST answer |
| `mandate` | the domain's mandate, which opens §1 of its contract | none: the user MUST answer |
| `handles` | the kinds of request the domain owns, each a `kind` with its `examples` | `[]` |
| `entry_skills` | the skills the dispatcher may name in a delegation | `[]` |
| `exposure` | for each entry skill, the risks it carries, of `private_data`, `untrusted_content`, and `sends_outward` | `{}` |
| `sensitive` | whether the domain holds sensitive data, such as accounts or legal papers | `false` |
| `policy` | the keys of `policy` that the core's `README.md` names | `{}`: no network host, no allowed command |
| `unattended` | what a scheduled or background run may do: `read-only` or `none` | `none` if `sensitive`; otherwise `read-only` |
| `vault` | whether the domain gets a vault: `true`, `false`, or the name of a new folder | `true`: a folder named after the domain |
| `folders` | each other folder in `~/Documents` the domain works on, existing or new: a `name`, an `access` of `read` or `write`, and an optional `sensitive` | `[]` |

**A sensitive domain runs with no network host by default.** If `sensitive`
is `true` and the user names a network host, ask the user to confirm the
host.

**A folder of a sensitive domain is sensitive.** If `sensitive` is `true`,
the script marks every folder `sensitive`.

## 2. Make the domain

1. Write the answers as one JSON object to a file in the session
   scratchpad.
2. Run `python3 .claude/skills/new-domain/scripts/new_domain.py create <answers>`
   from the repository root. If the user names the domain's directory, pass
   it with `--into`. Otherwise the script makes `~/Developer/<name>`.
3. Read the JSON the command prints.

The script takes these steps:

1. It checks the manifest the answers make. If `domain.py` would refuse the
   manifest, the script writes nothing.
2. It copies the domain template, and drops the suffix `.template` from
   each file name.
3. It commits the copy, and vendors the branch `core` at
   `vendor/agent-core/` with `git subtree add --squash`.
4. It links every core unit into `.claude/` by a relative symlink.
5. It writes `domain.json` and the settings blocks that
   `vendor/agent-core/domain.py settings` prints for it.
6. It commits the result, and runs the folder step.

**The command writes outside the session's repository.** If the sandbox
denies a write, stop and ask the user to run the command in a terminal.

## 3. Handle the result

| The output carries | Do |
| --- | --- |
| `error` naming the answers file | fix the answer the error names with the user, then run the command again |
| `error` naming the directory | stop and ask the user: the directory holds files the template would overwrite, or uncommitted changes |
| `error` from git | stop and ask the user, and name the directory the command left |
| `folders.refused` | tell the user that the folders exist only once the folder step runs on the primary |
| `folders.created` | report each folder, whether it existed, and the vault config files it received |

**Report the settings blocks.** The output's `settings` holds the
`permissions` and `sandbox` blocks the script wrote into
`<directory>/.claude/settings.json`.

**The new domain has no remote.** Tell the user to create its GitHub
repository and push `main`.

## 4. The folder step on an existing domain

**The folder step adds folders to a domain that already exists.** It also
creates on the primary each folder the manifest lists.

1. Write the answers `vault`, `folders`, and `sensitive` to a file in the
   session scratchpad. If the manifest already names a vault, set `vault`
   to `false`: the script refuses a second vault.
2. Run `python3 .claude/skills/new-domain/scripts/new_domain.py folders <answers> --domain <directory>`.
3. If the output carries `error`, write nothing more. Fix the answer the
   error names, and run step 2 again.
4. Write the printed `settings` blocks into
   `<directory>/.claude/settings.json` with the Write tool.

**The folder step NEVER overwrites a file.** It copies each file of the
domain's `obsidian/` into the vault's `.obsidian/` only if the vault lacks
the file.
