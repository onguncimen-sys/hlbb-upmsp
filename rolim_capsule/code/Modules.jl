#=
This file is used to modularize each metaheuristic to have its own global environment
=#
# RELEASE ADAPTATION: the original capsule used CodeOcean container paths ("/code/...")
# and the development copy used machine-specific paths; in this release copy the includes
# are FILE-RELATIVE (Julia resolves include() against the directory of the including file),
# so the capsule runs from wherever it is unpacked. Pristine original: Modules.jl.orig.

module ALNS
    include("Algorithms/ALNS-TS/ALNS-TS.jl")
    export Main_ALNS
end

module FACL
    include("Algorithms/FACL/FACL.jl")
    export Main_FACL
end

module FSS
    include("Algorithms/FSS/FSS.jl")
    export Main_FSS
end

module GA
    include("Algorithms/GA/GA.jl")
    export Main_GA
end

module GALA
    include("Algorithms/GALA/GALA.jl")
    export Main_GALA
end

module HABC
    include("Algorithms/HABC/HABC.jl")
    export Main_HABC
end

module HGA
    include("Algorithms/HGA/HGA.jl")
    export Main_HGA
end

module MSA
    include("Algorithms/MSA/MultiStart.jl")
    export Main_MSA
end

module SA
    include("Algorithms/SA/SA.jl")
    export Main_SA
end

module SSAFA
    include("Algorithms/SSAFA/SSAFA.jl")
    export Main_SSAFA
end

module VNSaiNet
    include("Algorithms/VNS-AiNet/VNS-aiNet.jl")
    export Main_VNS
end

module WOAFA
    include("Algorithms/WOAFA/WOAFA.jl")
    export Main_WOAFA
end