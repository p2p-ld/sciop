# Maintained by hand. Try to avoid creating the need to add lots of things to
# it.

{ rustPlatform }:

self: super: {

  content-negotiation = super.buildPythonPackage rec {
    pname = "content-negotiation";
    version = "1.1.2";

    src = super.fetchPypi {
      inherit pname version;
      hash = "sha256-Vh7VyuBls3VNxobHGochotTKcEuc5/3IdvgEil2xpw8=";
    };
  };

  fastapi-pagination = super.buildPythonPackage rec {
    pname = "fastapi-pagination";
    version = "0.12.34";

    src = super.fetchPypi {
      pname = "fastapi_pagination";
      inherit version;
      hash = "sha256-Be6MC8VyByFg9/MJAL/YeGnhiAyHvFeXki/sLknmXxE=";
    };

    pyproject = true;

    nativeBuildInputs = with self; [
      poetry-core
    ];

    propagatedBuildInputs = with self; [
      pydantic
      typing-extensions
    ];
  };

  fasthx = super.buildPythonPackage rec {
    pname = "fasthx";
    version = "2.3.1";

    src = super.fetchPypi {
      inherit pname version;
      hash = "sha256-PGU4CT2kqExmXwWise2kffsEv7zZa+8+GE26PNXFx4A=";
    };

    pyproject = true;

    nativeBuildInputs = with self; [
      poetry-core
    ];

    propagatedBuildInputs = with self; [
      fastapi
    ];
  };

  flatbencode = super.buildPythonPackage rec {
    pname = "flatbencode";
    version = "0.2.1";

    src = super.fetchPypi {
      inherit pname version;
      hash = "sha256-dzl9XQEIg1QE9vfK1kDUA8cCWhGBKvx+HfSw+SWJunc=";
    };
  };

  nh3 = super.buildPythonPackage rec {
    pname = "nh3";
    version = "0.2.21";

    src = super.fetchPypi {
      inherit pname version;
      hash = "sha256-SZDn7mpVSQ2/ANYab0dsmjJY4x5xHhNxOy6n1mFvZw4=";
    };

    pyproject = true;

    cargoDeps = rustPlatform.fetchCargoVendor {
      inherit src;
      name = "${pname}-${version}";
      hash = "sha256-1Ytca/GiHidR8JOcz+DydN6N/iguLchbP8Wnrd/0NTk=";
    };

    nativeBuildInputs = with rustPlatform; [
      cargoSetupHook
      maturinBuildHook
    ];
  };

  torf = super.buildPythonPackage rec {
    pname = "torf";
    version = "4.3.0";

    src = super.fetchPypi {
      inherit pname version;
      hash = "sha256-bSqHJo29Qe9QOfrxHL+AVXX+F8nR3/LrDkL+xoefLv8=";
    };

    pyproject = true;

    nativeBuildInputs = with self; [
      setuptools
    ];

    propagatedBuildInputs = with self; [
      flatbencode
    ];
  };
}
