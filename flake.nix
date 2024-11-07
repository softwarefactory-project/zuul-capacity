# Build release with: nix -L build .#release
{
  description = "The LogJuicer app";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = inputs@{ self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python311.withPackages
          (ps: [ ps.openstacksdk ps.prometheus-client ps.pyyaml ]);
        container-name = "ghcr.io/tristancacqueray/zuul-capacity";
        container = pkgs.dockerTools.streamLayeredImage {
          name = container-name;
          tag = "latest";
          created = "now";
          config.Entrypoint =
            [ "${python}/bin/python3" "${self}/zuul-capacity.py" ];
          config.Labels = {
            "org.opencontainers.image.source" =
              "https://github.com/tristancacqueray/zuul-capacity";
          };
        };

      in {
        packages.container = container;
        devShell = pkgs.mkShell { buildInputs = with pkgs; [ uv ]; };
      });
}
