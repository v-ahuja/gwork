function gw
  # `contains` avoids `test`, which would parse a leading flag such as -b or -d
  # in $argv[1] as one of its own operators.
  if contains -- "$argv[1]" --help -h
    command gwork --help
    return $status
  end

  set -l worktree_path (command gwork $argv)
  set -l rc $status

  if test $rc -ne 0
    return $rc
  end

  if test -z "$worktree_path"
    return 0
  end

  if test -d "$worktree_path"
    cd "$worktree_path"; or return 1
  end
end

function _gw_complete
  git for-each-ref --format='%(refname:short)' refs/heads/ 2>/dev/null
  git for-each-ref --format='%(refname:lstrip=3)' refs/remotes/ 2>/dev/null \
    | grep -v '^HEAD$' | sort -u
end

complete -c gw -l print-shell-integration -d 'print shell helper script'
complete -c gw -l install-shell-integration -d 'append shell integration to your shell rc file'
complete -c gw -l shell-integration-alias -d 'override shell helper name for printed integration'
complete -c gw -o new -d 'open worktree in a new iTerm2 tab/window/split pane'
complete -c gw -o b -d 'create new branch and worktree'
complete -c gw -o base -d 'update base branch before creating a new branch'
complete -c gw -o d -d 'remove worktree and delete branch'
complete -c gw -o D -d 'force-remove worktree and delete branch'
complete -c gw -f -a '(_gw_complete)' -d 'branch'
complete -c gwork -l print-shell-integration -d 'print shell helper script'
complete -c gwork -l install-shell-integration -d 'append shell integration to your shell rc file'
complete -c gwork -l shell-integration-alias -d 'override shell helper name for printed integration'
complete -c gwork -o new -d 'open worktree in a new iTerm2 tab/window/split pane'
complete -c gwork -o b -d 'create new branch and worktree'
complete -c gwork -o base -d 'update base branch before creating a new branch'
complete -c gwork -o d -d 'remove worktree and delete branch'
complete -c gwork -o D -d 'force-remove worktree and delete branch'
complete -c gwork -f -a '(_gw_complete)' -d 'branch'
complete -c git-gwork -l print-shell-integration -d 'print shell helper script'
complete -c git-gwork -l install-shell-integration -d 'append shell integration to your shell rc file'
complete -c git-gwork -l shell-integration-alias -d 'override shell helper name for printed integration'
complete -c git-gwork -o new -d 'open worktree in a new iTerm2 tab/window/split pane'
complete -c git-gwork -o b -d 'create new branch and worktree'
complete -c git-gwork -o base -d 'update base branch before creating a new branch'
complete -c git-gwork -o d -d 'remove worktree and delete branch'
complete -c git-gwork -o D -d 'force-remove worktree and delete branch'
complete -c git-gwork -f -a '(_gw_complete)' -d 'branch'
