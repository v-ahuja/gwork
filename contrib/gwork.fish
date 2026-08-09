function gw
  set -l worktree_path (command gwork $argv)
  set -l rc $status

  if test $rc -ne 0
    if test (count $worktree_path) -gt 0
      printf '%s\n' $worktree_path
    end
    return $rc
  end

  if test (count $worktree_path) -eq 1; and test -d "$worktree_path[1]"
    cd "$worktree_path[1]"; or return 1
  else if test (count $worktree_path) -gt 0
    printf '%s\n' $worktree_path
  end
end

function _gw_complete
  set -l tokens (commandline -opc)
  if test (count $tokens) -eq 1
    echo co
  end
  git for-each-ref --format='%(refname:short)' refs/heads/ 2>/dev/null
  git for-each-ref --format='%(refname:lstrip=3)' refs/remotes/ 2>/dev/null \
    | grep -v '^HEAD$' | sort -u
end

complete -c gw -l print-shell-integration -d 'print shell helper script'
complete -c gw -l install-shell-integration -d 'append shell integration to your shell rc file'
complete -c gw -l shell-integration-alias -d 'override shell helper name for printed integration'
complete -c gw -l version -d 'print version and exit'
complete -c gw -o v -d 'print version and exit'
complete -c gw -o new -d 'open worktree in a new iTerm2 tab/window/split pane'
complete -c gw -o b -d 'create new branch and worktree'
complete -c gw -o base -d 'update base branch before creating a new branch'
complete -c gw -o d -d 'remove worktree and delete branch'
complete -c gw -o D -d 'force-remove worktree and delete branch'
complete -c gw -f -a '(_gw_complete)' -d 'branch'
complete -c gwork -l print-shell-integration -d 'print shell helper script'
complete -c gwork -l install-shell-integration -d 'append shell integration to your shell rc file'
complete -c gwork -l shell-integration-alias -d 'override shell helper name for printed integration'
complete -c gwork -l version -d 'print version and exit'
complete -c gwork -o v -d 'print version and exit'
complete -c gwork -o new -d 'open worktree in a new iTerm2 tab/window/split pane'
complete -c gwork -o b -d 'create new branch and worktree'
complete -c gwork -o base -d 'update base branch before creating a new branch'
complete -c gwork -o d -d 'remove worktree and delete branch'
complete -c gwork -o D -d 'force-remove worktree and delete branch'
complete -c gwork -f -a '(_gw_complete)' -d 'branch'
complete -c git-gwork -l print-shell-integration -d 'print shell helper script'
complete -c git-gwork -l install-shell-integration -d 'append shell integration to your shell rc file'
complete -c git-gwork -l shell-integration-alias -d 'override shell helper name for printed integration'
complete -c git-gwork -l version -d 'print version and exit'
complete -c git-gwork -o v -d 'print version and exit'
complete -c git-gwork -o new -d 'open worktree in a new iTerm2 tab/window/split pane'
complete -c git-gwork -o b -d 'create new branch and worktree'
complete -c git-gwork -o base -d 'update base branch before creating a new branch'
complete -c git-gwork -o d -d 'remove worktree and delete branch'
complete -c git-gwork -o D -d 'force-remove worktree and delete branch'
complete -c git-gwork -f -a '(_gw_complete)' -d 'branch'
