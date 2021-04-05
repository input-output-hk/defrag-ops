{ sources ? import ./sources.nix, system ? __currentSystem }:
let
  nodePkgs = import sources.cardano-node { gitrev = sources.cardano-node.rev; };
  walletPkgs =
    import sources.cardano-wallet { gitrev = sources.cardano-wallet.rev; };
in with {
  overlay = self: super: {
    inherit (import sources.niv { }) niv;
    inherit (nodePkgs) cardano-cli;
    inherit (walletPkgs) bech32 cardano-address cardano-wallet cardano-tx;
  };
};
import sources.nixpkgs {
  overlays = [ overlay ];
  inherit system;
  config = { };
}
