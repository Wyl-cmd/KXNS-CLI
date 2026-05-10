{
  description = "kxns-cli flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixpkgs-unstable";
    systems.url = "github:nix-systems/default";
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      systems,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
    }:
    let
      allSystems = import systems;
      forAllSystems =
        f:
        nixpkgs.lib.genAttrs allSystems (
          system:
          let
            pkgs = import nixpkgs {
              inherit system;
              config.allowUnfree = true;
            };
          in
          f { inherit system pkgs; }
        );
    in
    {
      packages = forAllSystems (
        { pkgs, ... }:
        let
          kxns-cli =
            let
              inherit (pkgs)
                lib
                callPackage
                python313
                runCommand
                ripgrep
                stdenvNoCC
                makeWrapper
                versionCheckHook
                ;
              python = python313;
              pyproject = lib.importTOML ./pyproject.toml;
              workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
              overlay = workspace.mkPyprojectOverlay {
                sourcePreference = "wheel";
              };
              extraBuildOverlay = final: prev: {
                ripgrepy = prev.ripgrepy.overrideAttrs (old: {
                  nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [ final.setuptools ];
                });
                "kimi-code" = prev."kimi-code".overrideAttrs (old: {
                  postPatch = (old.postPatch or "") + ''
                    rm -f README.md
                    cp ${./README.md} README.md
                  '';
                });
              };
              pythonSet = (callPackage pyproject-nix.build.packages { inherit python; }).overrideScope (
                lib.composeManyExtensions [
                  pyproject-build-systems.overlays.wheel
                  overlay
                  extraBuildOverlay
                ]
              );
              kxnsCliPackage = pythonSet.mkVirtualEnv "kxns-cli-virtual-env-${pyproject.project.version}" workspace.deps.default;
            in
            stdenvNoCC.mkDerivation ({
              pname = "kxns-cli";
              version = pyproject.project.version;

              dontUnpack = true;

              nativeBuildInputs = [ makeWrapper ];
              buildInputs = [ ripgrep ];

              installPhase = ''
                runHook preInstall

                mkdir -p $out/bin
                makeWrapper ${kxnsCliPackage}/bin/kxns $out/bin/kxns \
                  --prefix PATH : ${lib.makeBinPath [ ripgrep ]} \
                  --set KXNS_CLI_NO_AUTO_UPDATE "1"

                runHook postInstall
              '';

              nativeInstallCheckInputs = [
                versionCheckHook
              ];
              versionCheckProgramArg = "--version";
              doInstallCheck = true;

              meta = {
                description = "KXNS Hunter CLI - A penetration testing focused AI agent CLI tool";
                license = lib.licenses.asl20;
                sourceProvenance = with lib.sourceTypes; [ fromSource ];
                mainProgram = "kxns";
              };
            });
        in
        {
          inherit kxns-cli;
          default = kxns-cli;
        }
      );

      devShells = forAllSystems (
        { pkgs, ... }:
        let
          inherit (pkgs) lib callPackage python313 ripgrep uv;
          python = python313;
          workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
          overlay = workspace.mkPyprojectOverlay {
            sourcePreference = "wheel";
          };
          pythonSet = (callPackage pyproject-nix.build.packages { inherit python; }).overrideScope (
            lib.composeManyExtensions [
              pyproject-build-systems.overlays.wheel
              overlay
            ]
          );
          venv = pythonSet.mkVirtualEnv "kxns-cli-dev-env" workspace.deps.all;
        in
        {
          default = pkgs.mkShell {
            packages = [
              python
              uv
              ripgrep
              pkgs.pyright
              pkgs.ruff
              pkgs.nixfmt-tree
            ];

            shellHook = ''
              export VIRTUAL_ENV="${venv}"
              export PATH="${venv}/bin:$PATH"
              export KXNS_CLI_NO_AUTO_UPDATE="1"
              echo "KXNS CLI development environment activated"
              echo "Python: $(python --version)"
              echo "uv: $(uv --version)"
            '';
          };
        }
      );

      formatter = forAllSystems ({ pkgs, ... }: pkgs.nixfmt-tree);
    };
}
