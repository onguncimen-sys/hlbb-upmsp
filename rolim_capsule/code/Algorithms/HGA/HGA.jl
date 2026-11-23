#=
* Implementation of the Genetic Algorithm of Adan (2022).
* Journal of Intelligent Manufacturing 33 (2022) 2059–2073
* Problem: Unrelated parallel machine scheduling with sequence-dependent setup times
* Objective: Makespan
* Coded by Gustavo Alencar Rolim - Universidade de São Paulo (2022/2023)
=#

using Random

# ================= NIS KATMANI (elig M_j + ready r_l) =================
# TUM eklemeler PURE-MODDA NO-OP -> _niche_pure=true iken guard'lar tetiklenmez,
# RNG-akisi pure HGA ile BIREBIR ayni (equivalence testi dogrular). Main_HGA'da
# _set_niche! ile aktive edilir. NOT: CrossOver eligibility'yi YAPISAL korur
# (offspring machine i = parents' machine i -> a job never changes machine index),
# guard yalnizca is YERLESTIREN/TASIYAN yerlerde: GreedyHeuristic, Insertion, Swap.
_READY = Int32[]                 # r_l (pure: zeros(m))
_ELIG = Vector{Bool}[]           # _ELIG[job][mach] (pure: bos, kullanilmaz)
_niche_pure = true               # true -> elig guard'lari no-op

function _set_niche!(m::Int, n::Int, r, M)
    global _READY, _ELIG, _niche_pure
    _READY = Int32[Int32(r === nothing ? 0 : r[l]) for l in 1:m]
    _niche_pure = (M === nothing)
    _ELIG = _niche_pure ? Vector{Bool}[] :
            Vector{Bool}[Bool[M[j][l] == 1 for l in 1:m] for j in 1:n]
end

@inline _ok(job::Integer, mach::Integer) = _niche_pure || _ELIG[job][mach]   # pure: hep true

# [AYAR 2026-10-10, on-kayit protokolu madde 4] DeltaIns duzeltme bayragi: araya eklemede eski
# komsu yayinin cikarilmasi. Varsayilan 0 = yayimlanmis davranis (birebirlik); kiyas kosularinda 1.
const DELTAINS_FIX = get(ENV, "DELTAINS_FIX", "0") == "1"
# =====================================================================

mutable struct Ind
    Sol::Vector{Vector{Int16}}
    OF::Vector{Int32}

    Ind() = new(Vector{Vector{Int16}}[], Vector{Int32}[])
end

function MachineSpan(Sol::Vector{Vector{Int16}}, M::Int8, p::Matrix{Int16},
    S::Vector{Matrix{Int16}})
    #----- Calculates the makespan of a given machine

    Span::Int32 = _READY[M]    # NIS: ready-time r_l (pure: 0)
    size::Int16 = length(Sol[M])

    for j in 1:size 
        if j != size
            Span += p[M, Sol[M][j]] + S[M][Sol[M][j], Sol[M][j+1]]
        else
            Span += p[M, Sol[M][j]]
        end
    end

    return(Span)
end

function GreedyHeuristic(m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Initializes a solution with a greedy criterion

    Sol = Vector{Int16}[[] for i in 1:m]
    OF = Int32[_READY[i] for i in 1:m]   # NICHE: empty-machine span = r_l (pure: zeros)
    U = collect(Int16, 1:n)
    shuffle!(U)
    C::Int16 = n

    while C != 0
        B::Int32 = 999999999
        M::Int8 = 0
        POS::Int16 = 0 

        for i::Int8 in 1:m
            if !_ok(U[1], i); continue; end   # NIS: uygunsuz makineyi atla (pure: no-op)
            size::Int16 = length(Sol[i])+1
            for j in 1:size
                insert!(Sol[i], j, U[1])

                NOF = MachineSpan(Sol, i, p, S)
                Inc::Int32 = NOF - OF[i]

                if Inc < B 
                    B = Inc 
                    M = i 
                    POS = j 
                end

                deleteat!(Sol[i], j)
            end
        end
        
        insert!(Sol[M], POS, U[1])
        popfirst!(U)
    
        OF[M] += B

        C -= 1
    end

    return(Sol, OF)
end

function InitPopulation(m::Int8, n::Int16, P::Int8,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Initializes population 

    POP = Ind[]

    for i in 1:P
        push!(POP, Ind())
        POP[i].Sol, POP[i].OF = GreedyHeuristic(m, n, p, S)
    end

    return(POP)
end

function PartialLS(MJ::Vector{Vector{Int16}}, O::Vector{Vector{Int16}}, m::Int8, 
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Adds missing jobs with a partial local search

    OF = zeros(Int32, m)
    NI::Int64 = 0

    for i::Int8 in 1:m 
        size::Int16 = length(MJ[i])
        isize::Int16 = length(O[i])+1

        while size != 0
            POS::Int16 = 0
            B::Int32 = 999999999

            for j in eachindex(MJ[i])
                for k in 1:isize 
                    insert!(O[i], k, MJ[i][1])
                    Cmax::Int32 = MachineSpan(O, i, p, S)
                    NI += 1

                    if Cmax < B 
                        B = Cmax
                        POS = k
                    end

                    deleteat!(O[i], k)
                end
            end
            
            insert!(O[i], POS, MJ[i][1])
            popfirst!(MJ[i])
            isize += 1
            size -= 1
        end
    end

    for i::Int8 in 1:m 
        OF[i] = MachineSpan(O, i, p, S)
        NI += 1
    end

    return(OF, NI)
end

function CrossOver(POP::Vector{Ind}, P::Int8, m::Int8,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Generates a new offspring 

    P1::Int8 = rand(1:P)
    P2::Int8 = rand(1:P)
    NI::Int64 = 0

    while P1 == P2 
        P2 = rand(1:P)
    end

    O1 = Ind()
    O2 = Ind()
    O1.Sol = Vector{Int16}[[] for i in 1:m]
    O2.Sol = Vector{Int16}[[] for i in 1:m]

    #----- Copy jobs from P1

    for i in 1:m
        size::Int16 = length(POP[P1].Sol[i])

        if size > 0 
            COP::Int16 = rand(1:size)
            O1.Sol[i] = deepcopy(POP[P1].Sol[i][1:COP])
            O2.Sol[i] = deepcopy(POP[P1].Sol[i][COP+1:size])
        end
    end

    #----- Finds missing jobs

    E1 = reduce(vcat, O1.Sol)
    E2 = reduce(vcat, O2.Sol)
    MJ1 = Vector{Int16}[[] for i in 1:m]
    MJ2 = Vector{Int16}[[] for i in 1:m]

    for i in 1:m 
        for j in POP[P2].Sol[i]
            if !(j in E1)
                push!(MJ1[i], j)
            end
            if !(j in E2)
                push!(MJ2[i], j)
            end 
        end
    end

    #----- Adds missing jobs 

    O1.OF, auxNI = PartialLS(MJ1, O1.Sol, m, p, S)

    NI += auxNI

    O2.OF, auxNI = PartialLS(MJ2, O2.Sol, m, p, S)

    NI += auxNI

    return(O1, O2, NI)
end

function DeltaIns(O::Ind, MR::Int8, MI::Int8, PR::Int16, PI::Int16, 
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Fast calculation of the machine span in the insertion neighborhood

    Cbi::Int32 = O.OF[MR] # Cost before insertion of machine i (job removal)
    Cbj::Int32 = O.OF[MI] # Cost before insertion of machine j (job insertion)
    Cai::Int32 = Cbi # Cost after insertion of machine i (job removal)
    Caj::Int32 = Cbj # Cost after insertion of machine j (job insertion)
    J::Int16 = O.Sol[MR][PR] # Job to be removed and then inserted
    SR::Int16 = length(O.Sol[MR]) # Length of the busiest machine 
    SI::Int16 = length(O.Sol[MI]) # Length of the machine with a lower span

    #----- Calculates the new span after job removal on the busiest machine
    
    if SR > 1
        if PR == 1
            Cai -= p[MR, J] + S[MR][J, O.Sol[MR][PR+1]]
        elseif PR == SR
            Cai -= S[MR][O.Sol[MR][PR-1], J] + p[MR, J]
        else
            Cai -= S[MR][O.Sol[MR][PR-1], J] + p[MR, J] + S[MR][J, O.Sol[MR][PR+1]]
            Cai += S[MR][O.Sol[MR][PR-1], O.Sol[MR][PR+1]]
        end
    else
        Cai -= p[MR, J]
    end

    #----- Calculates the new span after job insertion on the machine with a lower span

    if SI >= 1
        if PI == 1
            Caj += p[MI, J] + S[MI][J, O.Sol[MI][1]]
        elseif PI == SI+1
            Caj += S[MI][O.Sol[MI][PI-1], J] + p[MI, J]
        else
            Caj += S[MI][O.Sol[MI][PI-1], J] + p[MI, J] + S[MI][J, O.Sol[MI][PI]]
            if DELTAINS_FIX
                Caj -= S[MI][O.Sol[MI][PI-1], O.Sol[MI][PI]]
            end
        end
    else
        Caj += p[MI, J]
    end

    #----- Evaluates the move

    a::Int32 = 0

    if max(Cbi, Cbj) > max(Cai, Caj) 
        a = (Cbi - Cai) + (Cbj - Caj)
    end
    
    return(a)
end

function ExecuteIns(O::Ind, MR::Int8, MI::Int8, PR::Int16, PI::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Executes the insertion movement

    JOB::Int16 = O.Sol[MR][PR]
    deleteat!(O.Sol[MR], PR)
    insert!(O.Sol[MI], PI, JOB)

    #----- Updates the spans

    O.OF[MR] = MachineSpan(O.Sol, MR, p, S)
    O.OF[MI] = MachineSpan(O.Sol, MI, p, S)
end

function Insertion(O::Ind, m::Int8, p::Matrix{Int16}, 
    S::Vector{Matrix{Int16}}, dins::Float16)
    #----- Insertion neighborhood

    ngh::Int8 = floor(m * dins) # Number of sub-neighborhoods to be explored
    iprv::Bool = true # Tracks if there are improvements in the neighborhood
    NI::Int64 = 0
    
    while iprv == true
        l = sortperm(O.OF, rev = true) # Sorts the machines in descending order
        MR::Int8 = l[1] # Index of the busiest machine (contains the jobs to be removed)
        M::Int8 = 0 # Machine to insert the selcted job
        PR::Int16 = 0 # Best removal position 
        PI::Int16 = 0 # Best insertion position 
        B::Int32 = 999999999 # best movement
        iprv = false
        
        for i::Int8 in 2:1+ngh
            MI::Int8 = l[i] # Index of sub-neighborhoods to insert jobs
            size::Int16 = length(O.Sol[MI])+1
           
            for j::Int16 in eachindex(O.Sol[MR])
                if !_ok(O.Sol[MR][j], MI); continue; end   # NIS: is MI'ye uygun mu (pure: no-op)
                for k::Int16 in 1:size

                    a = DeltaIns(O, MR, MI, j, k, p, S)
                    NI += 1
    
                    if a != 0 && a < B 
                        B = a
                        PR = j 
                        PI = k
                        M = MI
                        iprv = true
                    end
                end
            end
    
            if iprv == true
                ExecuteIns(O, MR, M, PR, PI, p, S)
                NI += 2
                break
            end
        end
    end

    return(NI)
end

function DeltaSwap(O::Ind, M1::Int8, M2::Int8, S1::Int16, S2::Int16, 
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Fast calculation of the machine span in the swap neighborhood

    Cbi::Int32 = O.OF[M1] # Cost before swap of machine i 
    Cbj::Int32 = O.OF[M2] # Cost before swap of machine j 
    Cai::Int32 = Cbi # Cost after swap of machine i 
    Caj::Int32 = Cbj # Cost after swap of machine j
    J1::Int16 = O.Sol[M1][S1] # Job to swap on the busiest machine
    J2::Int16 = O.Sol[M2][S2] # Job to swap on the less busy machine
    SR::Int16 = length(O.Sol[M1]) # Length of the busiest machine 
    SI::Int16 = length(O.Sol[M2]) # Length of the machine with a lower span

    #----- Calculates the new span after the job swap on the busiest machine

    if SR > 1
        if S1 == 1
            Cai -= p[M1, J1] + S[M1][J1, O.Sol[M1][S1+1]]
            Cai += p[M1, J2] + S[M1][J2, O.Sol[M1][S1+1]]
        elseif S1 == SR
            Cai -= S[M1][O.Sol[M1][S1-1], J1] + p[M1, J1] 
            Cai += S[M1][O.Sol[M1][S1-1], J2] + p[M1, J2]
        else
            Cai -= S[M1][O.Sol[M1][S1-1], J1] + p[M1, J1] + S[M1][J1, O.Sol[M1][S1+1]]
            Cai += S[M1][O.Sol[M1][S1-1], J2] + p[M1, J2] + S[M1][J2, O.Sol[M1][S1+1]]
        end
    else
        Cai -= p[M1, J1]
        Cai += p[M1, J2]
    end

    #----- Calculates the new span after the job swap on the less busy machine

    if SI > 1
        if S2 == 1
            Caj -= p[M2, J2] + S[M2][J2, O.Sol[M2][S2+1]]
            Caj += p[M2, J1] + S[M2][J1, O.Sol[M2][S2+1]]
        elseif S2 == SI
            Caj -= S[M2][O.Sol[M2][S2-1], J2] + p[M2, J2]
            Caj += S[M2][O.Sol[M2][S2-1], J1] + p[M2, J1]
        else
            Caj -= S[M2][O.Sol[M2][S2-1], J2] + p[M2, J2] + S[M2][J2, O.Sol[M2][S2+1]]
            Caj += S[M2][O.Sol[M2][S2-1], J1] + p[M2, J1] + S[M2][J1, O.Sol[M2][S2+1]]
        end
    else
        Caj -= p[M2, J2]
        Caj += p[M2, J1]
    end

    #----- Evaluates the move

    a::Int32 = 0

    if max(Cbi, Cbj) > max(Cai, Caj)  
        a = (Cbi - Cai) + (Cbj - Caj)
    end
    
    return(a)
end

function DeltaN(O::Ind, M::Int8, P1::Int16, P2::Int16, size::Int16, S::Vector{Matrix{Int16}})
    #----- Fast calculation of the machine span in the nearest neighborhood

    C::Int32 = O.OF[M] # Cost before reinsertion 
    J::Int16 = O.Sol[M][P1] # Job to be reinserted

    #----- Remove the setup from the current position 

    if P1 == 1
        C -= S[M][J, O.Sol[M][P1+1]]
    elseif P1 == size
        C -= S[M][O.Sol[M][P1-1], J]
    else
        C -= S[M][O.Sol[M][P1-1], J] + S[M][J, O.Sol[M][P1+1]]
        C += S[M][O.Sol[M][P1-1], O.Sol[M][P1+1]]
    end

    #----- Add the new setup costs

    if P2 == 1
        C += S[M][J, O.Sol[M][P2]]
    elseif P2 == size
        C += S[M][O.Sol[M][P2], J]
    else
        if P1 > P2
            C -= S[M][O.Sol[M][P2-1], O.Sol[M][P2]]
            C += S[M][O.Sol[M][P2-1], J] + S[M][J, O.Sol[M][P2]]
        else
            C -= S[M][O.Sol[M][P2], O.Sol[M][P2+1]]
            C += S[M][O.Sol[M][P2], J] + S[M][J, O.Sol[M][P2+1]]
        end
    end

    a::Int32 =  O.OF[M] - C
    
    return(a)
end

function ExecuteReins(O::Ind, MR::Int8, P1::Int16, P2::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Executes the reinsertion movement

    J::Int16 = O.Sol[MR][P1]
    deleteat!(O.Sol[MR], P1)
    insert!(O.Sol[MR], P2, J)

    #----- Updates the spans

    O.OF[MR] = MachineSpan(O.Sol, MR, p, S)
end

function OptimizeSetup(O::Ind, Mj::Int8, POS::Int16, size::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Optimize the setup times in a sequence
    
    B::Int32 = -1 # Best movement
    Bpos::Int16 = 0 # Saves the best position
    iprv::Bool = false # Tracks if there are improvements in the sequence
    NI::Int64 = 0

    for i::Int16 in 1:size
        if i != POS
            a = DeltaN(O, Mj, POS, i, size, S)
            NI += 1

            if a != 0 && a > B
                B = a 
                Bpos = i
                iprv = true 
            end
        end
    end
    
    if iprv == true
        ExecuteReins(O, Mj, POS, Bpos, p, S)
        NI += 1
    end

    return(NI)
end

function ExecuteSwap(O::Ind, M1::Int8, M2::Int8, S1::Int16, S2::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Executes the swap movement

    J1::Int16 = O.Sol[M1][S1]
    J2::Int16 = O.Sol[M2][S2]
    O.Sol[M1][S1] = J2
    O.Sol[M2][S2] = J1
    NI::Int64 = 0

    #----- Updates the spans

    O.OF[M1] = MachineSpan(O.Sol, M1, p, S)
    O.OF[M2] = MachineSpan(O.Sol, M2, p, S)
    NI += 2

    #----- Optimize the sequence on machine Mj

    SMj::Int16 = length(O.Sol[M2])
    
    if SMj > 1
        NI += OptimizeSetup(O, M2, S2, SMj, p, S)
    end

    return(NI)
end

function Swap(O::Ind, m::Int8, p::Matrix{Int16}, 
    S::Vector{Matrix{Int16}}, dswap::Float16)
    #----- Swap neighborhood

    ngh::Int8 = floor(m * dswap) # Number of sub-neighborhoods to be explored
    iprv::Bool = true # Tracks if there are improvements in the neighborhood
    NI::Int64 = 0

    while iprv == true
        l = sortperm(O.OF, rev = true) # Sorts the machines in descending order
        M1::Int8 = l[1] # Index of the busiest machine
        M::Int8 = 0 # Machine to swap the jobs
        S1::Int16 = 0 # Best position of the job on the busiest machine
        S2::Int16 = 0 # Best position of the job on the less busy machine 
        B::Int32 = 0 # Best movement 
        iprv = false
        
        for i::Int8 in 2:1+ngh
            M2::Int8 = l[i] # Index of sub-neighborhoods to insert jobs
            size::Int16 = length(O.Sol[M2])
            
            for j::Int16 in eachindex(O.Sol[M1])
                for k::Int16 in 1:size
                    # NIS: swap sonrasi J1->M2, J2->M1 ikisi de uygun olmali (pure: no-op)
                    if !(_ok(O.Sol[M1][j], M2) && _ok(O.Sol[M2][k], M1)); continue; end

                    a = DeltaSwap(O, M1, M2, j, k, p, S)
                    NI += 1
    
                    if a != 0 && a < B 
                        B = a
                        S1 = j 
                        S2 = k
                        M = M2
                        iprv = true
                    end
                end
            end

            if iprv == true
                NI += ExecuteSwap(O, M1, M, S1, S2, p, S)
                break
            end
        end
    end

    return(NI)
end

function NearestNeighbor(O::Ind, m::Int8, p::Matrix{Int16}, 
    S::Vector{Matrix{Int16}}, dnn::Float16)
    #----- Nearest neighborhood

    ngh::Int8 = floor(m * dnn) # Number of sub-neighborhoods to be explored
    iprv::Bool = true # Tracks if there are improvements in the neighborhood
    NI::Int64 = 0

    while iprv == true
        l = sortperm(O.OF, rev = true) # Sorts the machines in descending order
        P1::Int16 = 0 # Best position of the job on the busiest machine
        P2::Int16 = 0 # Best position of the job on the less busy machine
        MR::Int8 = 0 # Machine to execute the reinsertion
        B::Int32 = -1 # Best movement 
        iprv = false
        
        for i::Int8 in 1:1+ngh
            M::Int8 = l[i]
            size::Int16 = length(O.Sol[M])
            
            for j::Int16 in 1:size
                for k::Int16 in 1:size
                    if j != k  
                        a = DeltaN(O, M, j, k, size, S)
                        NI += 1

                        if a != 0 && a > B
                            B = a 
                            P1 = j 
                            P2 = k
                            MR = M
                            iprv = true 
                        end
                    end
                end
            end
            
            if iprv == true
                ExecuteReins(O, MR, P1, P2, p, S)
                NI += 1
                break
            end
        end
    end

    return(NI)
end

function LocalSearch(O::Ind, m::Int8, p::Matrix{Int16}, 
    S::Vector{Matrix{Int16}}, dnn::Float16, dins::Float16, 
    dswap::Float16)
    #----- Performs local search

    iprv::Bool = true
    Inc::Int32 = maximum(O.OF)
    NI::Int64 = 0

    while iprv == true
        iprv = false
        
        NI += Insertion(O, m, p, S, dins)

        NI += Swap(O, m, p, S, dswap)

        NI += NearestNeighbor(O, m, p, S, dnn)

        Cmax::Int32 = maximum(O.OF)
        
        if Cmax < Inc 
            Inc = Cmax
            iprv = true 
        end
    end

    return(NI)
end

function UpdatePopulation(O::Ind, POP::Vector{Ind})
    #----- Accepts a new individual into the population

    N::Bool = true # Checks whether the offspring is new or not
    W::Int32 = -1 # Saves the worst makespan value
    POS::Int32 = 0 # Saves the position of the worst individual

    for i::Int8 in eachindex(POP)     
        if POP[i].Sol == O.Sol
            N = false
        end

        Max::Int32 = maximum(POP[i].OF)
        
        if Max > W 
            W = Max
            POS = i
        end
    end

    if N == true && maximum(O.OF) < W
        deleteat!(POP, POS)
        insert!(POP, POS, O)
    end
end

function BestOF(POP::Vector{Ind})
    #----- Returns the best solution of the population 

    Cmax::Int32 = 999999999

    for i in eachindex(POP)
        Max::Int32 = maximum(POP[i].OF)

        if Max < Cmax
            Cmax = Max 
        end
    end

    return(Cmax)
end

function Main_HGA(m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, t::Int; r=nothing, M=nothing)
    #----- NIS: eligibility/ready aktive (r=M=nothing -> pure, guard'lar no-op)
    _set_niche!(Int(m), Int(n), r, M)

    #----- Parameter declaration

    # [AYAR 2026-10-10, on-kayit protokolu madde 4] parametreler disaridan verilebilir;
    # default = published value (behaviour is bit-identical when the env variable is unset).
    P::Int8 = parse(Int8, get(ENV, "HGA_P", "15"))
    dnn::Float16 = parse(Float16, get(ENV, "HGA_DNN", "0.8"))
    dins::Float16 = parse(Float16, get(ENV, "HGA_DINS", "0.8"))
    dswap::Float16 = parse(Float16, get(ENV, "HGA_DSWAP", "0.8"))
    I::Int32 = 0
    NI::Int64 = 0

    #----- Initializes the population 

    POP = InitPopulation(m, n, P, p, S)
    B = BestOF(POP)

    #----- Time variables

    Tmax::Float64 = convert(Float64, n) * convert(Float64, m) * convert(Float64, t)/2000
    elapsed::Float64 = 0
    ST::Float64 = time()
    tbest::Float64 = 0.0   # en iyiyi bulma ani (sn)

    while elapsed <= Tmax
        #----- Performs Crossover

        O1, O2, auxNI = CrossOver(POP, P, m, p, S)
        NI += auxNI

        #----- Neighborhood descent

        NI += LocalSearch(O1, m, p, S, dnn, dins, dswap)
        NI += LocalSearch(O2, m, p, S, dnn, dins, dswap)

        #----- Acceptance of new individuals in the population

        UpdatePopulation(O1, POP)
        UpdatePopulation(O2, POP)

        Cmax::Int32 = BestOF(POP)

        if Cmax < B
            B = Cmax
            tbest = time() - ST
        end

        I += 1
        elapsed = time() - ST
    end

    # [DIS-DENETIM] en iyi bireyin cizelgesi de donduruluyor (bkz SA.jl notu).
    # UpdatePopulation en KOTU bireyi degistirir (HGA.jl:650-653) -> elitisttir, en iyi birey
    # asla dusmez -> POP'un su anki en iyisi, raporlanan B'nin sahibidir.
    # This scan runs once, AFTER the timed loop; it steals nothing from the budget.
    _bi = argmin([maximum(POP[i].OF) for i in eachindex(POP)])
    return(B, I, NI, tbest, POP[_bi].Sol)
end