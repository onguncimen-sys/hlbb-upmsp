# hash:sha256:f00d94f710bc9691ae39c02a08c84b72f2d40acf5c9fa5dd7aaa077acc1f32b6
FROM registry.codeocean.com/codeocean/julia:1.7.0-ubuntu18.04

ARG DEBIAN_FRONTEND=noninteractive

RUN julia -e 'using Pkg; Pkg.add(PackageSpec(name="DelimitedFiles"))' \
    && julia -e 'using Pkg; Pkg.add(PackageSpec(name="Distributions", version="0.25.100"))' \
    && julia -e 'using Pkg; Pkg.add(PackageSpec(name="Hungarian", version="0.7.0"))' \
    && julia -e 'using Pkg; Pkg.add(PackageSpec(name="Random"))' \
    && julia -e 'using Pkg; Pkg.add(PackageSpec(name="StatsBase", version="0.34.0"))' \
    && julia -e 'using Pkg; Pkg.API.precompile()'
