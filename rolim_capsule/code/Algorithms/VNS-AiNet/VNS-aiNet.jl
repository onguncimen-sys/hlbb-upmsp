#=
* Implementation of the VNS-aiNet of Diana et al. (2021).
* Expert Systems with Applications 182 (2021) 115140
* Problem: Unrelated parallel machine scheduling with sequence-dependent setup times
* Objective: Makespan
* Coded by Gustavo Alencar Rolim - Universidade de São Paulo (2022/2023)
=#

using Random

mutable struct Cell
    Mat::Float16
    IM::Float16
    Bmut::Float16
    Fit::Float16
    OF::Int32
    Sol::Vector{Vector{Int16}}

    Cell() = new(0.0, rand(Float16), rand(Float16), 0.0, 0, Vector{Vector{Int16}}[])
end

function Schedule(m::Int8, n::Int16)
    #----- Creates random solutions 

    SOL = Vector{Int16}[[] for i in 1:m]

    U = collect(Int16, 1:n)
    Count::Int16 = n

    while Count != 0
        Pos::Int16 = rand(1:Count)
        Job::Int16 = U[Pos]
        M::Int8 = rand(1:m)

        push!(SOL[M], Job)
        deleteat!(U, Pos)

        Count -= 1
    end
    
    return(SOL)
end

function Makespan(Sol::Vector{Vector{Int16}},
    m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Calculates the makespan of an individual in the population 

    Cmax::Int32 = 0

    for i in 1:m
        size::Int16 = length(Sol[i])
        CT::Int32 = 0 

        for j in 1:size
            if j != size
                CT += p[i, Sol[i][j]] + S[i][Sol[i][j], Sol[i][j+1]]
            else
                CT += p[i, Sol[i][j]]
            end
        end

        if CT > Cmax
            Cmax = CT
        end
    end
    
    return(Cmax)
end

function MachineSpan(Sol::Vector{Vector{Int16}}, M::Int8, p::Matrix{Int16},
    S::Vector{Matrix{Int16}})
    #----- Calculates the makespan of a given machine

    Span::Int32 = 0
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

function EvaluateFitness(P::Vector{Cell}, nAB::Int8, alpha::Float16)
    #----- Evaluates the fitness of the entire population

    sort!(P, by = j -> j.OF)

    for i in 1:nAB
        Flike::Float16 = 1 - (i/nAB)
        P[i].Fit = alpha*Flike + (1-alpha)*P[i].Mat
    end
end

function InitPopulation(nAB::Int8, m::Int8, n::Int16, β::Float16,
    alpha::Float16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Initializes the population of cells

    P = Cell[]

    for i in 1:nAB 
        push!(P, Cell())
        P[i].Bmut *= β

        if P[i].Bmut < 1 
            while P[i].Bmut < 1 
                P[i].Bmut = rand(Float16) * β
            end
        end

        P[i].Sol = deepcopy(Schedule(m, n))
        P[i].OF = Makespan(P[i].Sol, m, p, S)
    end

    EvaluateFitness(P, nAB, alpha)
    
    return(P)
end

function GenerateClones(P::Vector{Cell}, Clones::Vector{Cell},
    nAB::Int8, nCmax::Int8)
    #----- Generates a population of clones

    FROM = Int8[]

    for i in 1:nAB
        nCp::Int8 = max(1, round(P[i].Fit*nCmax))

        for j in 1:nCp 
            push!(Clones, deepcopy(P[i]))
            push!(FROM, i)
        end
    end

    return(FROM)
end

function InsMutation(Sol::Vector{Vector{Int16}}, m::Int8)
    #----- Performs an insertion mutation on a clone

    M1::Int8 = rand(1:m) # Machine to remove job

    #----- Guarantees that at least one machine is not empty

    while length(Sol[M1]) == 0
        M1 = rand(1:m)
    end
    
    #----- Selects a random job and remove it from M1 

    POS1::Int16 = rand(1:length(Sol[M1]))
    JOB::Int16 = Sol[M1][POS1]
    deleteat!(Sol[M1], POS1)

    #----- Selects a machine to insert the job

    M2::Int8 = rand(1:m)
    POS2::Int16 = rand(1:length(Sol[M2])+1)
    insert!(Sol[M2], POS2, JOB)
end

function InsSwap(Sol::Vector{Vector{Int16}}, m::Int8)
    #----- Performs a swap mutation on a clone

    M1::Int8 = rand(1:m)
    M2::Int8 = rand(1:m)
    S1::Int16 = length(Sol[M1])

    while S1 == 0 
        M1 = rand(1:m)
        S1 = length(Sol[M1])
    end

    S2::Int16 = length(Sol[M2])

    while S2 == 0 
        M2 = rand(1:m)
        S2 = length(Sol[M2])
    end

    POS1::Int16 = rand(1:S1)
    POS2::Int16 = rand(1:S2)
    JOB1::Int16 = Sol[M1][POS1]
    JOB2::Int16 = Sol[M2][POS2]

    while JOB1 == JOB2
        M1 = rand(1:m)
        M2 = rand(1:m)
        S1 = length(Sol[M1])
    
        while S1 == 0 
            M1 = rand(1:m)
            S1 = length(Sol[M1])
        end
    
        S2 = length(Sol[M2])
    
        while S2 == 0 
            M2 = rand(1:m)
            S2 = length(Sol[M2])
        end
    
        POS1 = rand(1:S1)
        POS2 = rand(1:S2)
        JOB1 = Sol[M1][POS1]
        JOB2 = Sol[M2][POS2]
    end

    Sol[M1][POS1] = JOB2
    Sol[M2][POS2] = JOB1
end

function CloneMutation(Clones::Vector{Cell}, m::Int8,
    alpha::Float16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Applies mutation to the newly generated Clones

    eval::Int64 = 0

    for i in eachindex(Clones)
        Nmut::Int8 = round(max(1, Clones[i].Bmut * exp(-Clones[i].Fit)))

        for j in 1:Nmut
            r = rand(Float16)

            if r <= Clones[i].IM
                #----- Perform insertion mutation

                InsMutation(Clones[i].Sol, m)

            else
                #----- Perform swap mutation

                InsSwap(Clones[i].Sol, m)

            end
        end
    end

    for i in eachindex(Clones)
        Clones[i].OF = Makespan(Clones[i].Sol, m, p, S)
        eval += 1
    end

    size::Int8 = length(Clones)

    EvaluateFitness(Clones, size, alpha)

    return(eval)
end

function InternalInsertion(Sol::Vector{Vector{Int16}}, OF::Int32,
    m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Executes the internal insertion neighborhood (II)

    obj = zeros(Int32, m)
    eval::Int64 = 0

    for i::Int8 in 1:m 
        obj[i] = MachineSpan(Sol, i, p, S)
        eval += 1
    end

    Midx::Int8 = argmax(obj)
    Cmax::Int32 = OF
    RMV::Int16 = 0
    INS::Int16 = 0
    size::Int16 = length(Sol[Midx])

    for i in 1:size
        JOB::Int16 = Sol[Midx][i]
        deleteat!(Sol[Midx], i)

        for j in 1:size
            insert!(Sol[Midx], j, JOB)
            NCmax::Int32 = MachineSpan(Sol, Midx, p, S)
            eval += 1

            if NCmax < Cmax 
                RMV = i 
                INS = j
                Cmax = NCmax
                obj[Midx] = NCmax
            end

            deleteat!(Sol[Midx], j)
        end

        insert!(Sol[Midx], i, JOB)
    end

    if RMV != 0 && INS != 0 
        JOB = Sol[Midx][RMV]
        deleteat!(Sol[Midx], RMV)
        insert!(Sol[Midx], INS, JOB)
        Cmax = maximum(obj)
    end
    
    return(Cmax, eval)
end

function InternalSwap(Sol::Vector{Vector{Int16}}, OF::Int32,
    m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Executes the internal swap neighborhood (IS)

    obj = zeros(Int32, m)
    eval::Int64 = 0

    for i::Int8 in 1:m 
        obj[i] = MachineSpan(Sol, i, p, S)
        eval += 1
    end

    Midx::Int8 = argmax(obj)
    Cmax::Int32 = OF 
    size::Int16 = length(Sol[Midx])
    BJ1::Int16 = 0 
    BJ2::Int16 = 0

    for i in 1:size 
        JOB1::Int16 = Sol[Midx][i]

        for j in 1:size
            if i > j 
                JOB2::Int16 = Sol[Midx][j]
                Sol[Midx][i] = JOB2  
                Sol[Midx][j] = JOB1

                NCmax::Int32 = MachineSpan(Sol, Midx, p, S)
                eval += 1

                if NCmax < Cmax
                    BJ1 = i
                    BJ2 = j
                    Cmax = NCmax
                    obj[Midx] = NCmax
                end

                Sol[Midx][i] = JOB1  
                Sol[Midx][j] = JOB2
            end
        end
    end

    if BJ1 != 0 && BJ2 != 0
        TEMP::Int16 = Sol[Midx][BJ1]
        Sol[Midx][BJ1] = Sol[Midx][BJ2]
        Sol[Midx][BJ2] = TEMP
        Cmax = maximum(obj)
    end

    return(Cmax, eval)    
end

function ExternalInsertion(Sol::Vector{Vector{Int16}}, OF::Int32,
    m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Executes the external insertion neighborhood (EI)

    obj = zeros(Int32, m)
    eval::Int64 = 0

    for i::Int8 in 1:m 
        obj[i] = MachineSpan(Sol, i, p, S)
        eval += 1
    end

    Midx::Int8 = argmax(obj)
    Cmax::Int32 = OF
    size = length(Sol[Midx])
    L = Int8[]

    for i in 1:m
        if i != Midx
            push!(L, i)
        end
    end

    shuffle!(L)
    iprv::Bool = false
    RMV::Int16 = 0
    INS::Int16 = 0
    Best::Int32 = Cmax
    Mach::Int8 = 0
    C::Int8 = m-1

    while C != 0
        for i in 1:size
            JOB::Int16 = Sol[Midx][i]
            deleteat!(Sol[Midx], i)
            Mins::Int8 = L[1]
            Size_Mins::Int16 = length(Sol[Mins])+1
            PRV::Int32 = obj[Mins]
            NSpan1::Int32 = MachineSpan(Sol, Midx, p, S)
            eval += 1
            obj[Midx] = NSpan1

            for j in 1:Size_Mins
                insert!(Sol[Mins], j, JOB)
                NSpan2::Int32 = MachineSpan(Sol, Mins, p, S)
                eval += 1
                obj[Mins] = NSpan2
                NCmax::Int32 = maximum(obj)

                if NCmax < Best
                    iprv = true
                    RMV = i
                    INS = j 
                    Mach = Mins
                    Best = NCmax
                end

                deleteat!(Sol[Mins], j)
                obj[Mins] = PRV
            end

            insert!(Sol[Midx], i, JOB)
            obj[Midx] = Cmax
        end

        if iprv == true
            JOB = Sol[Midx][RMV]
            deleteat!(Sol[Midx], RMV)
            insert!(Sol[Mach], INS, JOB)
            Cmax = Best
            break
        end

        popfirst!(L)
        C -= 1
    end

    return(Cmax, eval)
end

function ExternalSwap(Sol::Vector{Vector{Int16}}, OF::Int32,
    m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Executes the external swap neighborhood (ES)

    obj = zeros(Int32, m)
    eval::Int64 = 0

    for i::Int8 in 1:m 
        obj[i] = MachineSpan(Sol, i, p, S)
        eval += 1
    end

    Midx::Int8 = argmax(obj) # Machine with the highest cost 
    Cmax::Int32 = OF # Makespan 
    size::Int16 = length(Sol[Midx])
    L = Int8[]

    for i in 1:m
        if i != Midx
            push!(L, i)
        end
    end

    shuffle!(L)
    
    iprv::Bool = false
    BJ1::Int16 = 0
    BJ2::Int16 = 0
    Best::Int32 = Cmax 
    Mach::Int8 = 0
    C::Int8 = m-1

    while C != 0
        for i in 1:size
            SWP1::Int16 = Sol[Midx][i]
            MI::Int8 = L[1]
            SMI::Int16 = length(Sol[MI])
            PRV::Int32 = obj[MI]

            for j in 1:SMI 
                SWP2::Int16 = Sol[MI][j]
                Sol[Midx][i] = SWP2
                Sol[MI][j] = SWP1

                NS1::Int32 = MachineSpan(Sol, Midx, p, S)
                eval += 1
                NS2::Int32 = MachineSpan(Sol, MI, p, S)
                eval += 1
                obj[Midx] = NS1
                obj[MI] = NS2
                NCmax::Int32 = maximum(obj)

                if NCmax < Best
                    iprv = true
                    BJ1 = i 
                    BJ2 = j
                    Mach = MI
                    Best = NCmax
                end

                obj[Midx] = Cmax
                obj[MI] = PRV
                Sol[Midx][i] = SWP1
                Sol[MI][j] = SWP2
            end
        end

        if iprv == true
            TEMP::Int16 = Sol[Midx][BJ1]
            Sol[Midx][BJ1] = Sol[Mach][BJ2]
            Sol[Mach][BJ2] = TEMP
            Cmax = Best
            break
        end

        popfirst!(L)
        C -= 1
    end

    return(Cmax, eval)
end

function LocalSearch(Clones::Vector{Cell}, alpha::Float16,
    m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Executes the VNS scheme

    LS::Int8 = 4
    eval::Int64 = 0

    for i in eachindex(Clones)
        C::Int8 = 1

        while C <= LS
            if C == 1
                #----- II neighborhood

                Clones[i].OF, ev = InternalInsertion(Clones[i].Sol, Clones[i].OF, m, p, S)
                eval += ev

            elseif C == 2 
                #----- IS neighborhood

                Clones[i].OF, ev = InternalSwap(Clones[i].Sol, Clones[i].OF, m, p, S)
                eval += ev

            elseif C == 3
                #----- EI neighborhood

                Clones[i].OF, ev = ExternalInsertion(Clones[i].Sol, Clones[i].OF, m, p, S)
                eval += ev

            elseif C == 4 
                #----- ES neighborhood

                Clones[i].OF, ev = ExternalSwap(Clones[i].Sol, Clones[i].OF, m, p, S)
                eval += ev

            end

            C += 1
        end
    end

    size::Int8 = length(Clones)

    EvaluateFitness(Clones, size, alpha)

    return(eval)
end

function EmptyCells(Clones::Vector{Cell})
    #----- Delete all elements from the list of clones

    size::Int8 = length(Clones)

    while size != 0
        popfirst!(Clones)
        size -= 1
    end
end

function UpdateFactors(P::Vector{Cell}, nAB::Int8,
    β::Float16, MatFac::Float16, FROM::Vector{Int8})
    #----- Update the factors Mat, IM, Bmut 

    for i in eachindex(P)
        if i <= nAB
            P[i].Mat += MatFac
            Fmat::Float16 = 1 - P[i].Mat
            P[i].Bmut = Fmat * P[i].Bmut + (1 - Fmat) * rand(Float16) * β
            P[i].IM = Fmat * P[i].IM + (1 - Fmat) * rand(Float16)
        else
            if P[i].OF < P[FROM[i-nAB]].OF
                P[i].Mat = 0 
            else
                P[i].Mat += MatFac
            end

            Fmat = 1 - P[i].Mat
            P[i].Bmut = Fmat * P[i].Bmut + (1 - Fmat) * rand(Float16) * β
            P[i].IM = Fmat * P[i].IM + (1 - Fmat) * rand(Float16)
        end
    end
end

function Maturation(P::Vector{Cell}, Ru::Vector{Cell})
    #----- Remove maturated cells from the current population

    for i in eachindex(P)
        if P[i].Mat >= 1
            push!(Ru, P[i])
        end
    end
    
    filter!(x -> x.Mat < 1, P)
end

function Affinity(Sol::Vector{Vector{Int16}}, NewPop::Vector{Cell}, m::Int8, n::Int16)
    #----- Calculates the affinity of the solution

    B::Int16 = 9999
    
    for i in eachindex(NewPop)
        Aff::Int16 = 0

        for j in 1:m 
            l1::Int16 = length(Sol[j])
            l2::Int16 = length(NewPop[i].Sol[j])

            if l1 == 0 && l2 != 0 
                Aff += 1

            elseif l1 == 1 && l2 == 1
                if Sol[j][1] != NewPop[i].Sol[j][1]
                    Aff += 1
                end

            else
                for k in 2:l2
                    if k <= l1 && l1 >= 2
                        if Sol[j][k] != NewPop[i].Sol[j][k] && Sol[j][k-1] != NewPop[i].Sol[j][k-1]
                            Aff += 1
                        end
                    else
                        break
                    end
                end
            end
        end

        if Aff < B
            B = Aff
        end 
    end

    Afcell::Float16 = B/n

    return(Afcell)
end

function SupressFit(P::Vector{Cell}, NewPop::Vector{Cell}, nAB::Int8, sigma::Float16,
    m::Int8, n::Int16)
    #----- Executes the supression by fitness

    if length(P) == 0 
        return
    end

    push!(NewPop, P[1])
    popfirst!(P)
    SPu::Int16 = length(NewPop)
    RMV = Int16[]

    for i::Int16 in eachindex(P)
        Afcell::Float16 = Affinity(P[i].Sol, NewPop, m, n)
       
        if Afcell < 1 - sigma
            push!(NewPop, P[i])
            push!(RMV, i)
            SPu += 1
        end

        if SPu >= nAB
            break
        end
    end
    
    deleteat!(P, RMV)
end

function AddRandomCells(NewPop::Vector{Cell}, nAB::Int8, β::Float16, alpha::Float16,
    m::Int8, n::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Adds random cells to the new population 

    L::Int8 = length(NewPop)
    eval::Int64 = 0

    if L == nAB
        return(eval)
    end

    NC::Int8 = nAB - L
    NewCells = Cell[]

    for i in 1:NC 
        push!(NewCells, Cell())
        NewCells[i].Bmut *= β

        if NewCells[i].Bmut < 1 
            while NewCells[i].Bmut < 1 
                NewCells[i].Bmut = rand(Float16) * β
            end
        end

        NewCells[i].Sol = deepcopy(Schedule(m, n))
        NewCells[i].OF = Makespan(NewCells[i].Sol, m, p, S)
        eval += 1
    end

    append!(NewPop, NewCells)
    EmptyCells(NewCells)
    EvaluateFitness(NewPop, nAB, alpha)

    return(eval)
end

function SupressOF(Mu::Vector{Cell}, Ru::Vector{Cell}, P::Vector{Cell}, 
    nAB::Int8, sigma::Float16, m::Int8, n::Int16)
    #----- Executes the supression by objective function 

    M = Cell[]

    #----- Union of the sets 

    append!(M, Mu)
    append!(M, Ru)
    append!(M, P)

    #----- Free the lists

    EmptyCells(Mu)
    EmptyCells(Ru)
    EmptyCells(P)

    #----- Sort according to objective

    sort!(M, by = j -> j.OF)

    #----- Supression

    push!(Mu, M[1])
    popfirst!(M)
    SMu::Int16 = 1

    #----- Adds cells according to the affinity values 

    for i::Int16 in eachindex(M)
        Afcell::Float16 = Affinity(M[i].Sol, Mu, m, n)

        if Afcell < 1 - sigma
            push!(Mu, M[i])
            SMu += 1
        end

        if SMu >= nAB
            break
        end
    end

    #----- Free list containing the sets

    EmptyCells(M)
end

function UpdatePopulation(P::Vector{Cell}, NewPop::Vector{Cell})
    #----- Updates the vector of the current population 

    for i in eachindex(NewPop)
        push!(P, deepcopy(NewPop[i]))
    end

    EmptyCells(NewPop)
end

function SupressFinal(P::Vector{Cell}, Mu::Vector{Cell}, nAB::Int8, sigma::Float16, 
    m::Int8, n::Int16)
    #----- Executes the final supression

    F = Cell[]

    #----- Union of the sets 

    append!(F, P)
    append!(F, Mu)

    #----- Free the lists

    EmptyCells(P)
    EmptyCells(Mu)

    #----- Sort according to objective

    sort!(F, by = j -> j.OF)

    #----- Supression

    push!(P, F[1])
    popfirst!(F)
    SF::Int16 = 1

    #----- Supression

    for i::Int16 in eachindex(F)
        Afcell::Float16 = Affinity(F[i].Sol, P, m, n)

        if Afcell < 1 - sigma
            push!(P, F[i])
            SF += 1
        end

        if SF >= nAB
            break
        end
    end

    EmptyCells(F)
end

function Main_VNS(m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, t::Int)

    nAB::Int8 = 10
    nCmax::Int8 = 4
    β::Float16 = 4.0
    alpha::Float16 = 0.4
    MatFac::Float16 = 0.03
    sigma::Float16 = 0.09

    #----- List declaration 

    Ru = Cell[]
    Mu = Cell[]
    Clones = Cell[]
    NewPop = Cell[]

    #----- Initializes the population 

    P = InitPopulation(nAB, m, n, β, alpha, p, S)
    B::Int32 = minimum(j -> j.OF, P)

    #----- The conversion avoids numerical errors in Julia 

    Tmax = convert(Float64, n) * convert(Float64, m) * convert(Float64, t)/2000
    elapsed::Float64 = 0
    ST::Float64 = time()
    I::Int64 = 0
    NI::Int64 = 0
    
    while elapsed <= Tmax
        #----- Generates clones WHILE

        FROM = GenerateClones(P, Clones, nAB, nCmax)

        #----- Applies a random mutation to clones 

        NI += CloneMutation(Clones, m, alpha, p, S)

        #----- Executes local search

        NI += LocalSearch(Clones, alpha, m, p, S)

        #----- Updates the current population with the clones 
    
        append!(P, Clones)
        EmptyCells(Clones)

        #----- Updates the factors of current population 

        UpdateFactors(P, nAB, β, MatFac, FROM)

        #----- Removes maturated cells

        Maturation(P, Ru)

        #----- Updates fitness

        L::Int8 = length(P)
        EvaluateFitness(P, L, alpha)

        #----- Fitness supression
        
        SupressFit(P, NewPop, nAB, sigma, m, n)
    
        #----- Adds random cells if necessary 

        NI += AddRandomCells(NewPop, nAB, β, alpha, m, n, p, S)
    
        #----- Immunological memory update 

        SupressOF(Mu, Ru, P, nAB, sigma, m, n)

        #----- Updatex the population 

        UpdatePopulation(P, NewPop)

        #----- Updates the best solution 

        CB1::Int32 = minimum(j -> j.OF, P)
        CB2::Int32 = minimum(j -> j.OF, Mu)
        Cbest::Int32 = min(CB1, CB2)

        if Cbest < B
            B = Cbest
        end
        
        I += 1
        elapsed = time() - ST
    end

    SupressFinal(P, Mu, nAB, sigma, m, n)

    Cbest = minimum(j -> j.OF, P)

    if Cbest < B
        B = Cbest
    end

    return(B, I, NI)
end