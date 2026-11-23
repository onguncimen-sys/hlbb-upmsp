#=
* Implementation of the Adaptive Large Neighborhood Search with Tabu Search and Learning Automata (ALNS-TS) of Fang et al.
* Knowledge-Based Systems 241 (2022) 108193
* Problem: Unrelated parallel machine scheduling with sequence-dependent setup times
* Objective: Makespan
* Coded by Gustavo Alencar Rolim - Universidade de São Paulo (2022/2023)
=#

using Random, Hungarian

include("Tabu.jl")
include("LS.jl")

function CountJobs(MAT::Matrix{Int16}, M::Int8, n::Int16)
    #----- Inserts an element at row M of MAT
    
    len::Int16 = 0 

    for i in 1:n 
        if MAT[M, i] != 0
            len += 1
        else
            break
        end
    end

    return(len)
end

function MachineSpan(sol::Matrix{Int16}, M::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})

    span::Int32 = 0
    len = CountJobs(sol, M, n)

    for j in 1:len
        if j != len
            span += p[M, sol[M, j]] + S[M][sol[M, j], sol[M, j+1]]
        else
            span += p[M, sol[M, j]]
        end
    end

    return(span)
end

function InsMat(MAT::Matrix{Int16}, M::Int8, INS::Int16, POS::Int16, n::Int16)
    #----- Inserts an element at row M of MAT

    len = CountJobs(MAT, M, n)

    if POS > n
        println("The position exceeds the size of the row")
        exit()
    elseif POS > len+1
        println("The requested position does not exist")
        exit()
    elseif len == n
        println("The row is already full")
        exit()
    elseif POS == 0 
        println("There is no index 0")
        exit()
    end

    if len == 0 
        MAT[M, 1] = INS 
    elseif len == 1 && POS == 1
        MAT[M, POS+1] = MAT[M, POS]
        MAT[M, POS] = INS
    else
        for i in len+1:-1:POS+1 
            MAT[M, i] = MAT[M, i-1]
        end
        MAT[M, POS] = INS
    end
end

function DelMat(MAT::Matrix{Int16}, M::Int8, n::Int16, POS::Int16)
    #----- Deletes an element from a position in the solution
    
    len = CountJobs(MAT, M, n)

    if POS > MAT[M, POS] == 0
        println("There is no job in position $POS")
        exit()
    end

    if POS == len
        MAT[M, POS] = 0
    else
        MAT[M, POS] = 0

        for j in POS:len-1
            nxt::Int16 = MAT[M, j+1]
            MAT[M, j] = nxt
            MAT[M, j+1] = 0
        end
    end
end

function Initialization(m::Int8, n::Int16, p::Matrix{Int16})
    #----- Generates a semigreedy initial solution

    gd::Float16 = 0.5 
    count::Int16 = n
    U = collect(Int16, 1:n)
    sol = zeros(Int16, m, n)

    while count != 0 
        alpha = rand(Float16)

        if alpha >= gd
            MAXP::Int16 = 9999
            JOB_POS::Int16 = 0 
            M::Int8 = 0 

            for j in eachindex(U)
                for i in 1:m
                    if p[i, U[j]] < MAXP
                        MAXP = p[i, U[j]]
                        M = i
                        JOB_POS = j
                    end
                end
            end

            POS::Int16 = CountJobs(sol, M, n)
            POS += 1
            
            InsMat(sol, M, U[JOB_POS], POS, n)
            deleteat!(U, JOB_POS)

        else
            M = rand(1:m)
            len = CountJobs(sol, M, n)
            POS = rand(1:len+1)
            JOB_POS = rand(1:count)
            InsMat(sol, M, U[JOB_POS], POS, n)
            deleteat!(U, JOB_POS)
        end

        count -= 1
    end

    return(sol)
end

function RandomRemoval(sol::Matrix{Int16}, m::Int8, n::Int16, Ne::Int16)
    #----- Randomly remove jobs from the current solution

    rmv = Int16[]
    k::Int16 = 1
    
    while k <= Ne
        M::Int8 = rand(1:m)
        len = CountJobs(sol, M, n)

        while len == 0
            M = rand(1:m)
            len = CountJobs(sol, M, n)
        end

        POS::Int16 = rand(1:len)
        push!(rmv, sol[M, POS])
        DelMat(sol, M, n, POS)
        k += 1
    end
    
    return(rmv)
end

function WorstCostRemoval(sol::Matrix{Int16}, m::Int8, n::Int16, Ne::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Removes the job with the highest cost from the current solution 

    rmv = Int16[]
    k::Int16 = 1 

    while k <= Ne
        POS_JOB::Int16 = 0
        COST::Int16 = 0
        MAX_COST::Int16 = -1
        M::Int8 = 0

        for i::Int8 in 1:m
            len = CountJobs(sol, i, n)
            if len != 0
                for j in 1:len
                    if j < len
                        COST = p[i, sol[i, j]] + S[i][sol[i, j], sol[i, j+1]]
                    else
                        COST = p[i, sol[i, j]]
                    end
    
                    if COST > MAX_COST
                        MAX_COST = COST 
                        POS_JOB = j
                        M = i
                    end
                end
            end
        end

        push!(rmv, sol[M, POS_JOB])
        DelMat(sol, M, n, POS_JOB)
        k += 1
    end

    return(rmv)
end

function WorstMachineRemoval(sol::Matrix{Int16}, m::Int8, n::Int16, Ne::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Removes the jobs from the machine with highest cost

    rmv = Int16[]
    nr::Int16 = Ne # Number of remaining jobs
    COF = zeros(Int32, m)

    while nr > 0
        for i::Int8 in 1:m 
            COF[i] = MachineSpan(sol, i, n, p, S)
        end

        M::Int8 = argmax(COF)
        len = CountJobs(sol, M, n)

        for j in 1:len
            h::Int16 = 1
            push!(rmv, sol[M, 1])
            DelMat(sol, M, n, h)
            nr -= 1
            
            if nr == 0 
                break
            end
        end
    end

    return(rmv)
end

function SemiGreedyRemoval(sol::Matrix{Int16}, m::Int8, n::Int16, Ne::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Uses a semigreedy strategy to remove jobs 

    rmv = Int16[]
    COST = zeros(Int32, n)
    M = zeros(Int8, n)

    for i::Int8 in 1:m
        len = CountJobs(sol, i, n)
        for j in 1:len
            M[sol[i, j]] = i
            if j < len
                COST[sol[i, j]] = p[i, sol[i, j]] + S[i][sol[i, j], sol[i, j+1]]
            else
                COST[sol[i, j]] = p[i, sol[i, j]]
            end
        end
    end
    
    l = sortperm(COST, rev = true)
    k::Int16 = 1

    while k <= Ne
        alpha::Int16 = ceil(0.5 * length(l))
        pos::Int16 = rand(1:alpha)
        push!(rmv, l[pos])
        
        for j::Int16 in 1:n 
            if sol[M[l[pos]], j] == l[pos]
                DelMat(sol, M[l[pos]], n, j)
                break
            end
        end

        deleteat!(l, pos)
        k += 1
    end
    
    return(rmv)
end

function HighestRemoval(sol::Matrix{Int16}, m::Int8, n::Int16, Ne::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Removes the job with the highest cost from each machine simultaneously 

    rmv = Int16[]
    PH = zeros(Int16, m)
    RMN::Int16 = Ne

    while RMN != 0
        for i::Int8 in 1:m
            len = CountJobs(sol, i, n)
            COST::Int32 = 0
            MAXCOST::Int32 = -1 

            if len != 0
                for j in 1:len
                    if j < len
                        COST = p[i, sol[i, j]] + S[i][sol[i, j], sol[i, j+1]]
                    else
                        COST = p[i, sol[i, j]]
                    end
    
                    if COST > MAXCOST
                        MAXCOST = COST 
                        PH[i] = j
                    end
                end
            end
            
        end
        
        
        for i::Int8 in 1:m
            if PH[i] != 0
                push!(rmv, sol[i, PH[i]])
                DelMat(sol, i, n, PH[i])
                PH[i] = 0
                RMN -= 1

                if RMN == 0 
                    break
                end
            end
        end
    end

    return(rmv)
end

function BestCostIns(sol::Matrix{Int16}, m::Int8, n::Int16, Ne::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, rmv::Vector{Int16})
    #----- Inserts the jobs in the minimum cost position

    OF = zeros(Int32, m)
    eval::Int64 = 0

    for i::Int8 in 1:m 
        OF[i] += MachineSpan(sol, i, n, p, S)
        eval += 1
    end

    k::Int16 = Ne

    while k != 0 
        M::Int8 = 0 
        POS::Int16 = 0 
        BEST::Int32 = 999999999
        for i::Int8 in 1:m 
            len = CountJobs(sol, i, n)

            for j::Int16 in 1:len+1
                InsMat(sol, i, rmv[1], j, n)
                OFN::Int32 = MachineSpan(sol, i, n, p, S)
                eval += 1
                INCR::Int32 = OFN - OF[i]
                
                if INCR < BEST
                    BEST = INCR
                    POS = j
                    M = i
                end

                DelMat(sol, i, n, j)
            end
        end
        
        InsMat(sol, M, rmv[1], POS, n)
        popfirst!(rmv)
        OF[M] += BEST
        k -= 1
    end

    return(eval)
end

function SemiGreedyIns(sol::Matrix{Int16}, m::Int8, n::Int16, Ne::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, rmv::Vector{Int16})
    #----- Inserts the jobs in the minimum cost position

    OF = zeros(Int32, m)
    eval::Int64 = 0 

    for i::Int8 in 1:m 
        OF[i] = MachineSpan(sol, i, n, p, S)
        eval += 1
    end

    NP::Int16 = n - Ne + m
    k::Int16 = Ne

    while k != 0
        INCR = zeros(Int32, NP)
        M = zeros(Int8, NP)
        POS = zeros(Int16, NP)
        count::Int16 = 1

        for i::Int8 in 1:m 
            len = CountJobs(sol, i, n)
            for j::Int16 in 1:len+1
                InsMat(sol, i, rmv[1], j, n)
                OFN = MachineSpan(sol, i, n, p, S)
                eval += 1
                INCR[count] = OFN - OF[i]
                M[count] = i 
                POS[count] = j
                count += 1
                DelMat(sol, i, n, j)
            end
        end

        l = sortperm(INCR)
        alpha::Int16 = ceil(0.5 * length(l))
        idx::Int16 = rand(1:alpha)
        InsMat(sol, M[l[idx]], rmv[1], POS[l[idx]], n)
        popfirst!(rmv)
        OF[M[l[idx]]] += INCR[l[idx]]

        NP += 1
        k -= 1
    end

    return(eval)
end

function LowMachineIns(sol::Matrix{Int16}, m::Int8, n::Int16, Ne::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, rmv::Vector{Int16})
    #----- Inserts the jobs in the best position of a random machine

    OF = zeros(Int32, m)
    eval::Int64 = 0 

    for i::Int8 in 1:m 
        OF[i] = MachineSpan(sol, i, n, p, S)
        eval += 1
    end

    k::Int16 = Ne 

    while k != 0 
        M::Int8 = rand(1:m)
        POS::Int16 = 0 
        BEST::Int32 = 999999999
        len = CountJobs(sol, M, n)

        for j::Int16 in 1:len+1 
            InsMat(sol, M, rmv[1], j, n)
            OFN::Int32 = MachineSpan(sol, M, n, p, S)
            eval += 1
            INCR::Int32 = OFN - OF[M]

            if INCR < BEST
                BEST = INCR
                POS = j
            end

            DelMat(sol, M, n, j)
        end

        InsMat(sol, M, rmv[1], POS, n)
        popfirst!(rmv)
        OF[M] += BEST
        k -= 1
    end

    return(eval)
end

function HungarianIns(sol::Matrix{Int16}, m::Int8, n::Int16, Ne::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, rmv::Vector{Int16})
    #----- Inserts the jobs according to the Hungarian method

    OF = zeros(Int32, m)
    eval::Int64 = 0

    for i::Int8 in 1:m 
        OF[i] = MachineSpan(sol, i, n, p, S)
        eval += 1
    end

    k::Int16 = Ne
    MAT = zeros(Int16, m, m)
    POS = zeros(Int16, m, m)

    while k != 0
        if length(rmv) >= m
            for a in 1:m 
                for i::Int8 in 1:m 
                    BEST::Int32 = 999999999
                    len = CountJobs(sol, i, n)
                    for j::Int16 in 1:len+1
                        InsMat(sol, i, rmv[a], j, n)
                        OFN::Int32 = MachineSpan(sol, i, n, p, S)
                        eval += 1
                        INCR::Int32 = OFN - OF[i]
                
                        if INCR < BEST
                            BEST = INCR
                            MAT[i, a] = INCR
                            POS[i, a] = j
                        end

                        DelMat(sol, i, n, j)
                    end
                end
            end

            ASS, cost = hungarian(MAT)
            
            for a::Int8 in 1:m
                M::Int8 = ASS[a]
                InsMat(sol, M, rmv[a], POS[M, a], n)
                OF[M] += MAT[M, a]
            end

            for a::Int8 in 1:m
                popfirst!(rmv)
                k -= 1
            end
        else
            R::Int16 = length(rmv)
            eval += SemiGreedyIns(sol, m, n, R, p, S, rmv)
            break
        end
    end

    return(eval)
end

function RegretIns(sol::Matrix{Int16}, m::Int8, n::Int16, Ne::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, rmv::Vector{Int16})
    #----- Inserts the job with highest regret cost

    OF = zeros(Int32, m)
    eval::Int64 = 0 

    for i::Int8 in 1:m 
        OF[i] = MachineSpan(sol, i, n, p, S)
        eval += 1 
    end

    k::Int16 = Ne
    REGRET = zeros(Int16, Ne)
    REFM = zeros(Int8, Ne)
    REFP = zeros(Int16, Ne)
    B = Int32[i = 999999999 for i in 1:Ne]
    COST = Int16[]

    while k != 0
        for J in eachindex(rmv)
            for i::Int8 in 1:m
                len = CountJobs(sol, i, n)
                for j::Int16 in 1:len+1
                    InsMat(sol, i, rmv[J], j, n)
                    OFN::Int32 = MachineSpan(sol, i, n, p, S)
                    eval += 1
                    INCR::Int32 = OFN - OF[i]
                    
                    if INCR < B[J]
                        B[J] = INCR
                        REFM[J] = i 
                        REFP[J] = j
                    end
                    
                    DelMat(sol, i, n, j)
                    push!(COST, INCR)
                end
            end

            if length(REGRET) > 1
                l = sortperm(COST)
                REGRET[J] = COST[l[2]] - COST[l[1]]
            else
                REGRET[J] = 0
            end
            
            SIZE::Int16 = length(COST)
            
            while SIZE != 0
                popfirst!(COST)
                SIZE -= 1
            end
        end
        
        list = sortperm(REGRET, rev = true)
        InsMat(sol, REFM[list[1]], rmv[list[1]], REFP[list[1]], n)
        deleteat!(rmv, list[1])
        OF[REFM[list[1]]] = B[list[1]]
        popfirst!(REGRET)
        popfirst!(REFP)
        popfirst!(REFM)
        popfirst!(B)
        
        for i in eachindex(REGRET)
            REGRET[i] = 0
            REFM[i] = 0
            REFP[i] = 0
            B[i] = 999999999
        end
        
        k -= 1
    end

    return(eval)
end

function RedefineSol(sol::Matrix{Int16}, n::Int16, m::Int8)
    #----- Redifines the soution representation scheme

    NSol = zeros(Int16, n+m-1)
    count::Int16 = 1
    mc::Int8 = -1

    for i in 1:m 
        for j in 1:n 
            if sol[i, j] != 0
                NSol[count] = sol[i, j]
                count += 1
            else
                break
            end
        end
        if i < m
            NSol[count] = mc
            mc += -1
            count += 1
        end
    end
    
    return(NSol)
end

function Init_Sol(sol::Vector{Int16}, n::Int16, m::Int8)
    #----- Redifines the solution to execute Destroy/Repair Swaps

    NSol = zeros(Int16, m, n)
    mc::Int8 = 1
    pc::Int16 = 1

    for i in 1:n+m-1
        if sol[i] > 0
            NSol[mc, pc] = sol[i]
            pc += 1
        else
            mc += 1
            pc = 1
        end
    end
            
    return(NSol)
end

function SelectMethod(w::Vector{Float64})
    #----- Selects a destruction/repair operator

    len::Int8 = length(w)
    WSum::Float16 = sum(w)
    r::Int32 = rand(1:ceil(WSum))
    CSum::Int32 = 0
    method::Int8 = 0

    for i in 1:len
        CSum += w[i]

        if CSum >= r
            method = i
            break
        end

        if i == len && CSum < r
            method = i
        end

    end

    return(method)
end

function Destroy(sol::Matrix{Int16}, m::Int8, n::Int16, Ne::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, D::Int8)
    #----- Calls the repair heuristics

    if D == 1 
        rmv = RandomRemoval(sol, m, n, Ne)
    elseif D == 2
        rmv = WorstCostRemoval(sol, m, n, Ne, p, S)
    elseif D == 3
        rmv = WorstMachineRemoval(sol, m, n, Ne, p, S)
    elseif D == 4
        rmv = SemiGreedyRemoval(sol, m, n, Ne, p, S)
    elseif D == 5
        rmv = HighestRemoval(sol, m, n, Ne, p, S)
    end

    return(rmv)
end

function Repair(sol::Matrix{Int16}, m::Int8, n::Int16, Ne::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, R::Int8, rmv::Vector{Int16})
    #----- Calls the removal heuristics

    eval::Int64 = 0

    if R == 1 
        eval += BestCostIns(sol, m, n, Ne, p, S, rmv)
    elseif R == 2
        eval += SemiGreedyIns(sol, m, n, Ne, p, S, rmv)
    elseif R == 3
        eval += LowMachineIns(sol, m, n, Ne, p, S, rmv)
    elseif R == 4
        eval += HungarianIns(sol, m, n, Ne, p, S, rmv)
    elseif R == 5
        eval += RegretIns(sol, m, n, Ne, p, S, rmv)
    end

    return(eval)
end

function UpdateProb(w::Vector{Float64}, a::Float64, b::Float64, sel::Int8, Beta::Bool)
    #----- Update the score of the weights

    r::Int8 = length(w)

    if Beta == true
        for i in eachindex(w)
            if i == sel 
                w[i] = w[i] + a*(1 - w[i])
            else
                w[i] = w[i] * (1-a)
            end
        end
    else 
        for i in eachindex(w)
            if i == sel
                w[i] = w[i] * (1-b)
            else
                w[i] = (b/(r-1)) + (w[i] * (1 - b))
            end
        end
    end

    SUM::Float64 = sum(w)

    for i in eachindex(w)
        w[i] /= SUM 
    end
end

function UpdateLA(Ad::Vector{Float64}, Ar::Vector{Float64},
    wd::Vector{Float64}, wr::Vector{Float64})
    #----- Update Learning Automata

    for i in eachindex(Ad)
        Ad[i] = wd[i]
        Ar[i] = wr[i]
    end
end

function Main_ALNS(m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, t::Int)
    #----- Initial solution 
    
    sol = Initialization(m, n, p)
    OF = zeros(Int32, m)
    
    for i::Int8 in 1:m
        OF[i] = MachineSpan(sol, i, n, p, S)
    end

    Best::Int32 = maximum(OF)
    solB = deepcopy(sol)
   
    #----- Weights initialization

    wd = Float64[i = 0.2 for i in 1:5] # Probability of destruction operators
    wr = Float64[i = 0.2 for i in 1:5] # Probability of repair operators
    Ad = Float64[i = 0.2 for i in 1:5] # Automaton of destruction operators
    Ar = Float64[i = 0.2 for i in 1:5] # Automaton of repair operators

    #----- Parameter declaration

    q::Float64 = 0.1
    T0::Float64 = 1*((0.1*Best)/log(2))
    T::Float64 = T0
    Tb::Float64 = T0
    alpha::Float64 = 0.99
    noImp::Int16 = 0
    Iter::Int64 = 1
    TabuList = zeros(Int32, n+m-1, n+m-1)
    Ne::Int16 = ceil(q*n)
    a::Float64 = 0
    a1::Float64 = 0.2 
    a2::Float64 = 0.1
    a3::Float64 = 0.05
    b::Float64 = 0.02
    K::Int8 = 6 * max(length(wd), length(wr))
    Beta::Bool = false
    NI::Int64 = 0 

    #----- Time variables

    Tmax = convert(Float64, n) * convert(Float64, m) * convert(Float64, t)/2000
    elapsed::Float64 = 0
    ST::Float64 = time()
    
    while elapsed <= Tmax
        #----- Destroy and repair solution
        
        D::Int8 = rand(1:5) #SelectMethod(Ad)
        rmv = Destroy(sol, m, n, Ne, p, S, D)
        
        shuffle!(rmv)
        
        R::Int8 = rand(1:5) #SelectMethod(Ar)
        NI += Repair(sol, m, n, Ne, p, S, R, rmv)
        
        #----- Redefine solution representation
    
        sol = RedefineSol(sol, n, m)
    
        #----- Executes Tabu Search
    
        Cmax1, ev = TabuSearch(sol, m, n, p, S, Iter, TabuList, Best)
        NI += ev
        
        #----- New solution to apply local search
    
        NSOL = deepcopy(sol)
        
        #----- Executes local search
        
        Cmax2, ev = LocalSearch(NSOL, m, n, p, S, Iter)
        NI += ev
        
        #----- Acceptance criterion 
    
        if Cmax2 <= Best 
            Best = Cmax2 
            solB = deepcopy(NSOL)
            sol = deepcopy(NSOL)
            a = a1
            Beta = true
        elseif Cmax2 <= Cmax1
            Cmax1 = Cmax2 
            sol = deepcopy(NSOL)
            a = a2 
            b = 0
            noImp += 1
            Beta = true
        elseif rand() <= exp(-(Cmax1 - Cmax2)/T)
            Cmax1 = Cmax2 
            sol = deepcopy(NSOL)
            a = a3 
            b = 0 
            noImp += 1
            Beta = true
        else
            a = 0 
            b = b1
            noImp += 1
            Beta = false
        end
        
        #----- Change solution representation
        
        sol = Init_Sol(sol, n, m)
        
        #----- Update temperature
    
        T *= alpha 
    
        if T <= 0.01
            Tb *= 2
            T = min(Tb, T0)
        end
        
        #----- Update probabilities
    
        UpdateProb(wd, a, b, D, Beta)
        UpdateProb(wr, a, b, R, Beta)
    
        #----- Update the Learning Automata
        
        if Iter % K == 0
            UpdateLA(Ad, Ar, wd, wr)
        end
        
        q += 4/n*(0.0002*noImp)
        Dfac = ceil(q*n)  # Update destruction factor

        if Dfac > n 
            Ne = n 
        else
            Ne = Dfac
        end

        Iter += 1
        elapsed = time() - ST
    end
    
    return(Best, Iter, NI)
end