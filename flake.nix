{
  inputs = {
    nixpkgs = {
      type = "github";
      owner = "NixOS";
      repo = "nixpkgs";
      ref = "nixos-unstable";
    };

    pip2nix = {
      type = "github";
      owner = "nix-community";
      repo = "pip2nix";
    };
  };

  outputs = { self, nixpkgs, pip2nix, ... }:
  let supportedSystems = [ "aarch64-linux" "x86_64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      nixpkgsFor = forAllSystems (system: import nixpkgs { inherit system; });
  in {
    packages = forAllSystems (system:
    let pkgs = import nixpkgs {
          inherit system;
          overlays = [
            (self: super: {
              pythonPackagesExtensions = super.pythonPackagesExtensions ++ [
                (pkgs.callPackage ./python-packages.nix { })
              ];
            })
          ];
        };
    in rec {
      default = sciop;

      sciop = pkgs.python3Packages.buildPythonApplication rec {
        pname = "sciop";
        version = "0.1";

        src = ./.;

        pyproject = true;

        nativeBuildInputs = with pkgs.python3Packages; [
          pdm-backend
        ];

        propagatedBuildInputs = with pkgs.python3Packages; [
          aiodns
          alembic
          apscheduler
          bcrypt
          bencode-py
          content-negotiation
          faker
          fastapi
          fastapi-pagination
          fasthx
          humanize
          httpx
          lxml
          mkdocs-git-authors-plugin
          mkdocs-material
          mkdocs-redirects
          mistune
          nh3
          pydantic
          pydantic-settings
          pygments
          pyjwt
          pymdown-extensions
          #pytest-playwright-asyncio
          python-multipart
          python-slugify
          rdflib
          rich
          slowapi
          sqlmodel
          torf
          uvicorn
        ];
      };
    });

    devShells = forAllSystems (system: let pkgs = nixpkgsFor.${system}; in {
      default = pkgs.mkShell {
        nativeBuildInputs = with pkgs; [
          python3
          pip2nix.defaultPackage.${system}
        ];
      };
    });
  };
}
