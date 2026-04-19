gwork() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    command gwork --help
    return $?
  fi

  local path rc
  path="$(command gwork "$@")"
  rc=$?

  if (( rc != 0 )); then
    return "$rc"
  fi

  if [[ -n "$path" && -d "$path" ]]; then
    cd "$path" || return 1
  fi
}

_gw_complete() {
  if [[ "$PREFIX" == -* ]]; then
    local -a flags=(
      '--print-shell-integration:print shell helper script'
      '--install-shell-integration:append shell integration to your shell rc file'
      '-new:open worktree in a new iTerm2 tab/window/split pane'
      '-b:create new branch and worktree'
      '-base:update base branch before creating a new branch'
      '-d:remove worktree and delete branch'
      '-D:force-remove worktree and delete branch'
    )
    _describe 'flag' flags
    return
  fi

  local -a local_branches remote_branches branches
  local remote_branch

  local_branches=( ${(f)"$(git for-each-ref --format='%(refname:short)' refs/heads/ 2>/dev/null)"} )
  remote_branches=( ${(f)"$(git for-each-ref --format='%(refname:lstrip=3)' refs/remotes/ 2>/dev/null | grep -v '^HEAD$' | sort -u)"} )

  branches=( $local_branches )
  for remote_branch in $remote_branches; do
    if (( ! ${local_branches[(Ie)$remote_branch]} )); then
      branches+=( "$remote_branch" )
    fi
  done

  if [[ ${#words} -eq 2 ]]; then
    branches=( "co" $branches )
  fi

  _describe 'branch' branches
}

compdef _gw_complete gwork
compdef _gw_complete git-gwork
_git_gwork() { _gw_complete "$@"; }
