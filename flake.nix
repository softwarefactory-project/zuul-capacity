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

        info = builtins.fromTOML (builtins.readFile ./pyproject.toml);

        container-name = "ghcr.io/softwarefactory-project/zuul-capacity";
        container = pkgs.dockerTools.streamLayeredImage {
          name = container-name;
          tag = "latest";
          created = "now";
          config.Entrypoint =
            [ "${python}/bin/python3" "${self}/zuul-capacity.py" ];
          config.Labels = {
            "org.opencontainers.image.source" =
              "https://github.com/softwarefactory-project/zuul-capacity";
          };
        };

        publish-container-release =
          pkgs.writeShellScriptBin "container-release" ''
            set -e
            export PATH=$PATH:${pkgs.gzip}/bin:${pkgs.skopeo}/bin
            IMAGE="docker://${container-name}"

            echo "Logging to registry..."
            echo $GH_TOKEN | skopeo login --username $GH_USERNAME --password-stdin ghcr.io

            echo "Building and publishing the image..."
            ${container} | gzip --fast | skopeo copy docker-archive:/dev/stdin $IMAGE:${info.project.version}

            echo "Tagging latest"
            skopeo copy $IMAGE:${info.project.version} $IMAGE:latest
          '';

      in {
        packages.container = container;
        apps.publish-container-release =
          flake-utils.lib.mkApp { drv = publish-container-release; };
        devShell = pkgs.mkShell { buildInputs = with pkgs; [ uv ]; };
      });
}
