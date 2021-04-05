let pkgs = import ./nix { };
in with pkgs;
mkShell {
  buildInputs = with pkgs; [
    mypy
    niv
    nixfmt
    python3
    python3Packages.base58
    python3Packages.black
    python3Packages.docopt
    python3Packages.flake8
    python3Packages.ipython
    python3Packages.numpy
    python3Packages.requests
    python3Packages.semver
    shellcheck
  ];
}
