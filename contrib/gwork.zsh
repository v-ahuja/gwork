gw() {
  local worktree_path rc
  worktree_path="$(command gwork "$@")"
  rc=$?

  if (( rc != 0 )); then
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
  if [[ "$PREFIX" == -* ]]; then
    local -a flags=(
      '--print-shell-integration:print shell helper script'
      '--install-shell-integration:append shell integration to your shell rc file'
      '--shell-integration-alias:override shell helper name for printed integration'
      '--version:print version and exit'
      '-v:print version and exit'
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

compdef _gw_complete gw
compdef _gw_complete gwork
compdef _gw_complete git-gwork
_git_gwork() { _gw_complete "$@"; }
