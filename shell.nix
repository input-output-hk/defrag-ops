let pkgs = import ./nix { };
in with pkgs;
mkShell {
  buildInputs = with pkgs; [
    bash
    bech32
    cardano-address
    cardano-cli
    cardano-tx
    cardano-wallet
    coreutils
    curl
    jq
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
    sqlite-interactive
    xxd
  ];
  shellHook = ''
    # In this directory, make a text file named "cardano-node-socket-path.txt"
    # with the path to the cardano node socket file for automatic export
    # of the cardano node socket path
    if [ -r ./cardano-node-socket-path.txt ]; then
      export CARDANO_NODE_SOCKET_PATH=$(< cardano-node-socket-path.txt)
    fi
    source <(cardano-cli --bash-completion-script cardano-cli)
    source <(cardano-address --bash-completion-script cardano-address)
    source <(cardano-tx --bash-completion-script cardano-tx)
  '';
}
