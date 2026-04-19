gwork() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    command gwork --help
    return $?
  fi

  local path rc
  path="$(command gwork "$@")"
  rc=$?

  if [[ $rc -ne 0 ]]; then
    return "$rc"
  fi

  if [[ -n "$path" && -d "$path" ]]; then
    cd "$path" || return 1
  fi
}

_gw_complete() {
  local cur
  cur="${COMP_WORDS[COMP_CWORD]}"

  if [[ "$cur" == -* ]]; then
    COMPREPLY=( $(compgen -W "--print-shell-integration --install-shell-integration -new -b -base -d -D" -- "$cur") )
    return
  fi

  local local_branches remote_branches
  local_branches="$(git for-each-ref --format='%(refname:short)' refs/heads/ 2>/dev/null)"
  remote_branches="$(git for-each-ref --format='%(refname:lstrip=3)' refs/remotes/ 2>/dev/null | grep -v '^HEAD$' | sort -u)"
  COMPREPLY=( $(compgen -W "co ${local_branches} ${remote_branches}" -- "$cur") )
}

complete -F _gw_complete gwork
complete -F _gw_complete git-gwork
