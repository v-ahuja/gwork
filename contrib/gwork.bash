gw() {
  local worktree_path rc
  worktree_path="$(command gwork "$@")"
  rc=$?

  if [[ $rc -ne 0 ]]; then
    [[ -n "$worktree_path" ]] && printf '%s\n' "$worktree_path"
    return "$rc"
  fi

  if [[ -n "$worktree_path" && -d "$worktree_path" ]]; then
    cd "$worktree_path" || return 1
  elif [[ -n "$worktree_path" ]]; then
    printf '%s\n' "$worktree_path"
  fi
}

_gw_complete() {
  local cur
  cur="${COMP_WORDS[COMP_CWORD]}"

  if [[ "$cur" == -* ]]; then
    COMPREPLY=( $(compgen -W "--print-shell-integration --install-shell-integration --shell-integration-alias --version -v -new -b -base -d -D" -- "$cur") )
    return
  fi

  local local_branches remote_branches
  local_branches="$(git for-each-ref --format='%(refname:short)' refs/heads/ 2>/dev/null)"
  remote_branches="$(git for-each-ref --format='%(refname:lstrip=3)' refs/remotes/ 2>/dev/null | grep -v '^HEAD$' | sort -u)"
  COMPREPLY=( $(compgen -W "co ${local_branches} ${remote_branches}" -- "$cur") )
}

complete -F _gw_complete gw
complete -F _gw_complete gwork
complete -F _gw_complete git-gwork
