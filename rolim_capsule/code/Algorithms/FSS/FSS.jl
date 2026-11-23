#=
* Implementation of the Fixed Set Search (FSS) of Jovanovic and Voẞ.
* Applied Soft Computing 110 (2021) 107521
* Problem: Unrelated parallel machine scheduling with sequence-dependent setup times
* Objective: Makespan
* Coded by Gustavo Alencar Rolim - Universidade de São Paulo (2022/2023)
=#

using Random

mutable struct Ind 
    Sol::Vector{Vector{Int16}}
    OF::Vector{Int32}
    Fit::Int32

    Ind() = new(Vector{Vector{Int16}}[], Vector{Int32}[], 0)
end

function Makespan(sol::Vector{Vector{Int16}}, m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Calculates and returns the makespan of the solutio
    
    Cmax::Int32 = 0

    for i in 1:m 
        size::Int16 = length(sol[i])
        Ct::Int32 = 0

        for j in eachindex(sol[i])
            if j != size
                Ct += p[i, sol[i][j]] + S[i][sol[i][j], sol[i][j+1]]
            else
                Ct += p[i, sol[i][j]]
            end
        end

        if Ct > Cmax
            Cmax = Ct
        end
    end

    return(Cmax)
end

function MachineSpan(M::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}}, sol::Vector{Vector{Int16}})
    #----- Calculates and returns the makespan of a machine

    span::Int32 = 0
    size::Int16 = length(sol[M])

    for j in eachindex(sol[M])
        if j != size 
            span += p[M, sol[M][j]] + S[M][sol[M][j], sol[M][j+1]]
        else
            span += p[M, sol[M][j]]
        end
    end
    
    return(span)
end

function RGA(m::Int8, n::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}}, RLS::Int8)
    #----- Implementation of the randomized greedy algorithm 

    U = collect(Int16, 1:n)
    V = zeros(Int32, 4, n)
    sol = Vector{Int16}[[] for i in 1:m]
    Cmax = zeros(Int32, m)
    
    while length(U) != 0
        for job in eachindex(U)
            Best::Int32 = 999999999 
            for i::Int8 in 1:m
                last::Int16 = length(sol[i])+1 # Number of available positions in a machine
                for j in 1:last
                    insert!(sol[i], j, U[job])
                    A = MachineSpan(i, p, S, sol)
                    C::Int32 = A - Cmax[i]
                    Cmax[i] = A
                    H::Int32 = 10 * maximum(Cmax) + C

                    if H < Best 
                        Best = H 
                        V[1, job] = U[job]
                        V[2, job] = i
                        V[3, job] = j
                        V[4, job] = H
                    end

                    Cmax[i] -= C
                    deleteat!(sol[i], j)
                end
            end
        end
        
        L = sortperm(V[4, 1:end])

        if length(L) >= RLS
            r::Int8 = rand(1:RLS)
        else
            r = 1
        end

        JOB::Int16 = V[1, L[r]]
        M::Int8 = V[2, L[r]]
        POS::Int16 = V[3, L[r]]
        
        insert!(sol[M], POS, JOB)
        filter!(x -> x != JOB, U)
        Cmax[M] = MachineSpan(M, p, S, sol)
        V = V[:, 1:end .!= L[r]]
    end
    
    return(sol, Cmax)
end

function MachineSelect(sol::Vector{Vector{Int16}},m::Int8)
    #----- Selects twp different machines

    M1::Int8 = rand(1:m)

    while length(sol[M1]) == 0 
        M1 = rand(1:m)
    end

    M2::Int8 = rand(1:m)

    while length(sol[M2]) == 0 
        M2 = rand(1:m)
    end

    return(M1, M2)
end

function Swap(sol::Vector{Vector{Int16}}, Cmax::Vector{Int32}, m::Int8,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Swap neighborhood
   
    Inc = deepcopy(Cmax) # Incumbent solution
    iprv::Bool = false
    M1, M2 = MachineSelect(sol, m)
    eval::Int64 = 0

    POS1::Int16 = rand(1:length(sol[M1]))
    POS2::Int16 = rand(1:length(sol[M2]))
    JOB1::Int16 = sol[M1][POS1]
    JOB2::Int16 = sol[M2][POS2]

    sol[M1][POS1] = JOB2
    sol[M2][POS2] = JOB1

    for i::Int8 in 1:m
        Cmax[i] = MachineSpan(i, p, S, sol)
        eval += 1
    end

    if maximum(Cmax) > maximum(Inc)
        sol[M1][POS1] = JOB1 
        sol[M2][POS2] = JOB2
        for i in 1:m 
            Cmax[i] = Inc[i]
        end
    elseif maximum(Cmax) == maximum(Inc) && sum(Cmax) < sum(Inc)
        iprv = true
    elseif maximum(Cmax) < maximum(Inc)
        iprv = true
    end
   
    return(iprv, eval)
end

function Relocation(sol::Vector{Vector{Int16}}, Cmax::Vector{Int32},
    m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Relocation neighborhood

    Inc = deepcopy(Cmax)
    M1::Int8 = rand(1:m)
    M2::Int8 = rand(1:m)
    iprv::Bool = false
    eval::Int64 = 0

    while M1 == M2 
        M2 = rand(1:m)
    end

    len::Int16 = length(sol[M1])
    
    if len != 0
        POS1::Int16 = rand(1:len)
        JOB::Int16 = sol[M1][POS1]
        deleteat!(sol[M1], POS1)
        
        #----- Position to insert 

        POS2::Int16 = rand(1:length(sol[M2])+1)
        insert!(sol[M2], POS2, JOB)
        
        for i::Int8 in 1:m
            Cmax[i] = MachineSpan(i, p, S, sol)
            eval += 1
        end

        if maximum(Cmax) > maximum(Inc)
            deleteat!(sol[M2], POS2)
            insert!(sol[M1], POS1, JOB)
            for i in 1:m 
                Cmax[i] = Inc[i]
            end
        elseif maximum(Cmax) == maximum(Inc) && sum(Cmax) < sum(Inc)
            iprv = true
        elseif maximum(Cmax) < maximum(Inc)
            iprv = true
        end
    end
    
    return(iprv, eval)
end

function RelocationPath(sol::Vector{Vector{Int16}}, Cmax::Vector{Int32},
    m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}}, MaxLen::Int8)
    #----- Path relocation neighborhood
    
    Inc = deepcopy(Cmax)
    M::Int8 = rand(1:m)
    iprv::Bool = false
    FAC::Int8 = MaxLen
    size::Int16 = length(sol[M])
    eval::Int64 = 0

    if size <= MaxLen
        FAC = ceil(size * 0.5)
    end
    
    if size <= 3
        return(iprv, eval)
    end

    POS::Int16 = rand(1:size-FAC)
    INS::Int16 = rand(1:size-FAC)
    
    while INS == POS
        INS = rand(1:size-FAC+1)
    end

    PATH = sol[M][POS:POS+FAC-1]
    filter!(x -> !(x in PATH), sol[M])
    count1::Int16 = INS
    count2::Int8 = FAC

    while count2 != 0
        insert!(sol[M], count1, PATH[1])
        popfirst!(PATH)
        count1 += 1
        count2 -= 1
    end

    for i::Int8 in 1:m 
        Cmax[i] = MachineSpan(i, p, S, sol)
        eval += 1
    end

    if maximum(Cmax) > maximum(Inc)
        PATH = sol[M][INS:INS+FAC-1]
        filter!(x -> !(x in PATH), sol[M])
        count1 = POS
        count2 = FAC
    
        while count2 != 0
            insert!(sol[M], count1, PATH[1])
            popfirst!(PATH)
            count1 += 1
            count2 -= 1
        end

        for i in 1:m 
            Cmax[i] = Inc[i]
        end

    elseif maximum(Cmax) == maximum(Inc) && sum(Cmax) < sum(Inc)
        iprv = true
    elseif maximum(Cmax) < maximum(Inc)
        iprv = true
    end

    return(iprv, eval)
end

function LocalSearch(sol::Vector{Vector{Int16}}, Cmax::Vector{Int32}, m::Int8, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, MaxLen::Int8)
    #----- Performs the neighborhood search

    Imp = collect(Int8, 1:3)
    SIZE::Int8 = 3
    eval::Int64 = 0

    while SIZE != 0
        shuffle!(Imp)
        r::Int8 = rand(1:SIZE)
        iprv::Bool = false

        if Imp[r] == 1
            iprv, ev = Swap(sol, Cmax, m, p, S)
            eval += ev
        elseif Imp[r] == 2
            iprv, ev = Relocation(sol, Cmax, m, p, S)
            eval += ev
        elseif Imp[r] == 3
            iprv, ev = RelocationPath(sol, Cmax, m, p, S, MaxLen)
            eval += ev
        end

        if iprv == false 
            deleteat!(Imp, r)
            SIZE -= 1
        else
            Imp = collect(Int8, 1:3)
            SIZE = 3
        end
    end

    return(eval)
end

function InitialPopulation(Psize::Int8, RLS::Int8, MaxLen::Int8, m::Int8,
    n::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})

    POP = Ind[]

    for i in 1:Psize
        push!(POP, Ind())

        #----- Randomized greedy algorithm

        POP[i].Sol, POP[i].OF = RGA(m, n, p, S, RLS)

        #----- Local search 

        ev = LocalSearch(POP[i].Sol, POP[i].OF, m, p, S, MaxLen)

        #----- Update Fitness value 

        POP[i].Fit = maximum(POP[i].OF)

        #----- Adjust the solution representation to a fixed set

        for j in 1:m 
            insert!(POP[i].Sol[j], 1, -1) # Indicates the start of the sequence
            insert!(POP[i].Sol[j], length(POP[i].Sol[j])+1, -2) # Indicates the end of the sequence 
        end
    end

    return(POP)
end

function CountElements(m::Int8, n::Int16, Skn::Vector{Int64},
    POP::Vector{Ind}, B::Vector{Vector{Int16}})
    # This function counts the most frequent nodes in relation to the good solutions

    REF = zeros(Int16, n+2, n+2, m)

    for i in Skn
        for j in 1:m 
            lens::Int16 = length(POP[i].Sol[j]) 
            lenb::Int16 = length(B[j])

            for k in 1:lenb-1 
                if k < lens 
                    if POP[i].Sol[j][k] == B[j][k] && POP[i].Sol[j][k+1] == B[j][k+1]
                        Job1::Int16 = B[j][k]
                        Job2::Int16 = B[j][k+1]

                        if Job1 == -1
                            pos1::Int16 = 1 
                        elseif Job1 == -2 
                            pos1 = n+2
                        else
                            pos1 = Job1+1 
                        end
                        
                        if Job2 == -1
                            pos2::Int16 = 1 
                        elseif Job2 == -2 
                            pos2 = n+2
                        else
                            pos2 = Job2+1 
                        end    
                        
                        REF[pos1, pos2, j] += 1
                    end
                end
            end
        end
    end

    return(REF)
end

function PathJobs(Size::Int16, n::Int16, REF::Array{Int16, 3})
    #----- Generate the path jobs according to the base solution 

    F = Vector{Int16}[]
    Count::Int16 = Size

    while Count != 0
        POS = argmax(REF)
        Arc = Int16[]

        if REF[POS] != 0 
            job1::Int16 = POS[1]

            if job1 == 1 
                job1 = -1 
            elseif job1 == n+2
                job1 = -2
            else
                job1 -= 1
            end

            job2::Int16 = POS[2]

            if job2 == 1 
                job2 = -1 
            elseif job2 == n+2
                job2 = -2
            else
                job2 -= 1
            end

            Mach::Int8 = POS[3]

            push!(Arc, job1)
            push!(Arc, job2)
            push!(Arc, Mach)
            push!(F, Arc)
            REF[POS] = 0
        end

        Count -= 1
    end

    return(F)
end

function FixedSet(POP::Vector{Ind}, k::Int8, N::Int8, M::Int8,
    Coef::Float16, m::Int8, n::Int16)
    #----- Generates the Fixed Set 

    Size::Int16 = floor((2*m+n) * Coef) # Size of the base solution
    Skn = sortperm(POP, by = j -> j.Fit) # Order the best solutions
    Skn = Skn[1:N] # Generate the subset of best solutions
    Count::Int8 = N 

    while Count != k # Selects the random k best solutions
        r::Int8 = rand(1:Count)
        deleteat!(Skn, r)
        Count -= 1
    end

    # Selects the base solution  

    B = POP[rand(1:M)].Sol

    # Count the most frequent elements

    REF = CountElements(m, n, Skn, POP, B)

    # Separates the frequent elements from the base solution 

    F = PathJobs(Size, n, REF)

    return(F)
end

function ConnectPath(AP::Vector{Vector{Int16}}, P1::Int16, P2::Int16)
    #----- Connect two paths

    len1::Int16 = length(AP[P1])
    len2::Int16 = length(AP[P2])
    RMV = Int16[P1, P2]
    arc = Int16[]
    
    if AP[P1][1] == AP[P2][len2-1]

        arc = append!(AP[P2][1:len2-1], AP[P1][2:len1])

    elseif AP[P1][len1-1] == AP[P2][1]

        arc = append!(AP[P1][1:len1-1], AP[P2][2:len2])
    end
    
    deleteat!(AP, RMV)
    insert!(AP, 1, arc)
end

function DisjunctPaths(AP::Vector{Vector{Int16}})
    #----- No job should appear in two or more paths 

    flag::Bool = true 

    while flag == true
        flag = false
        P1::Int16 = 0 
        P2::Int16 = 0 

        for i in eachindex(AP)
            for j in eachindex(AP)
                if i != j
                    len1::Int16 = length(AP[i])
                    len2::Int16 = length(AP[j])

                    if len1 != 0 && len2 != 0 
                        if AP[i][len1] == AP[j][len2]
                            if AP[i][1] in AP[j][1:len2-1] || AP[i][len1-1] in AP[j][1:len2-1]
                                flag = true
                                P1 = i 
                                P2 = j 
                                break
                            end
                        end
                    end
                end
            end

            if flag == true 
                break
            end
        end

        if flag == true 
            ConnectPath(AP, P1, P2)
        end
    end
end

function InitialSchedule(m::Int8, AP::Vector{Vector{Int16}})
    #----- Build an initial schedule with the path jobs 
    
    sol = Vector{Int16}[[] for i in 1:m]
    RMV = Int16[]

    #------ Add the start nodes

    for i in eachindex(AP)
        len::Int16 = length(AP[i])
        if AP[i][1] == -1 
            for j in 1:len-1
                push!(sol[AP[i][len]], AP[i][j])
            end

            push!(RMV, i)
        end
    end

    deleteat!(AP, RMV)

    while length(RMV) != 0 
        popfirst!(RMV)
    end
    
    #----- Add the end nodes 
    
    for i in eachindex(AP)
        len = length(AP[i])
        if AP[i][len-1] == -2
            for j in 1:len-1
                push!(sol[AP[i][len]], AP[i][j])
            end

            push!(RMV, i)
        end
    end
   
    deleteat!(AP, RMV)

    while length(RMV) != 0 
        popfirst!(RMV)
    end
    
    #----- Remove possible job dublicates 

    for i in 1:m 
        sol[i] = union(sol[i])
    end

    #----- Add any possible start or end nodes
    
    for i in 1:m
        s::Bool = false 
        e::Bool = false

        for j in eachindex(sol[i])
            if sol[i][j] == -1 
                s = true 
            elseif sol[i][j] == -2
                e = true 
            end
        end

        if s == false 
            insert!(sol[i], 1, -1)
        end

        if e == false
            push!(sol[i], -2)
        end
    end

    return(sol)
end

function NormalJobs(sol::Vector{Vector{Int16}}, AP::Vector{Vector{Int16}}, m::Int8, n::Int16)
    #----- Generate the set of normal jobs

    AN = collect(Int16, 1:n)

    #----- Remove the elements from AN that are already in the partial solution 
   
    for i in 1:m
        AN = filter!(x -> !(x in sol[i]), AN)
    end

    #----- Remove the elements from AN that are already in the path jobs

    for i in eachindex(AP)
        AN = filter!(x -> !(x in AP[i][1:end-1]), AN)
    end
    
    return(AN)
end

function DecodeSolution(sol::Vector{Vector{Int16}}, m::Int8)
    #----- Removes start and end nodes temporarily

    for i in 1:m
        size::Int16 = length(sol[i])
        if size >= 2
            if sol[i][size] == -2 
                deleteat!(sol[i], size)
            end
            if sol[i][1] == -1 
                deleteat!(sol[i], 1)
            end
        end
    end
end

function UnscheduledJobs(AP::Vector{Vector{Int16}}, AN::Vector{Int16})
    #----- Generate the set of unsecheduled jobs

    len::Int16 = length(AP) + length(AN)
    U = Vector{Int16}[[] for i in 1:len]

    #----- Append both normal and path jobs
    
    for i in 1:len 
        if i <= length(AP)
            append!(U[i], AP[i])
        else
            push!(U[i], AN[i-length(AP)])
        end
    end
    
    return(U)
end

function RGF(AP::Vector{Vector{Int16}}, RLS::Int8, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Generates an intinal schedule with the path jobs
    
    DisjunctPaths(AP) # Path jobs 
    sol = InitialSchedule(m, AP) # Partial solution 
    AN = NormalJobs(sol, AP, m, n) # Normal jobs
    DecodeSolution(sol, m) # Decode the solution 
    U = UnscheduledJobs(AP, AN) # Set of unsecheduled jobs
    eval::Int64 = 0

    #----- Calculates the partial Makespan

    Cmax = zeros(Int32, m)

    for i::Int8 in 1:m
        Cmax[i] = MachineSpan(i, p, S, sol)
        eval += 1
    end

    #----- Semi-greedy heuristic

    len::Int16 = length(U)
    V = zeros(Int32, 4, len)
    
    while len != 0
        for job in eachindex(U)
            Best::Int32 = 999999999

            if length(U[job]) == 1
                for i::Int8 in 1:m
                    last::Int16 = length(sol[i])+1

                    for j in 1:last
                        insert!(sol[i], j, U[job][1])
                        A = MachineSpan(i, p, S, sol)
                        eval += 1
                        C::Int32 = A - Cmax[i]
                        Cmax[i] = A
                        H::Int32 = 10 * maximum(Cmax) + C
        
                        if H < Best 
                            Best = H 
                            V[1, job] = job
                            V[2, job] = i
                            V[3, job] = j
                            V[4, job] = H
                        end
    
                        Cmax[i] -= C
                        deleteat!(sol[i], j)
                    end
                end
            else
                #----- The path jobs should be inserted only at the edges 

                M::Int8 = U[job][end]

                for j in 1:2
                    if j == 2 
                        append!(sol[M], U[job][1:end-1])
                        A = MachineSpan(M, p, S, sol)
                        eval += 1
                        C::Int32 = A - Cmax[M]
                        Cmax[M] = A
                        H::Int32 = 10 * maximum(Cmax) + C

                        if H < Best 
                            Best = H 
                            V[1, job] = job
                            V[2, job] = M
                            V[3, job] = j
                            V[4, job] = H
                        end

                        Cmax[M] -= C
                        filter!(x -> !(x in U[job][1:end-1]), sol[M])
                    else
                        size::Int16 = length(U[job]) - 1
                        
                        for ins in 1:size
                            insert!(sol[M], ins, U[job][ins])
                        end

                        A = MachineSpan(M, p, S, sol)
                        eval += 1
                        C = A - Cmax[M]
                        Cmax[M] = A
                        H = 10 * maximum(Cmax) + C

                        if H < Best 
                            Best = H 
                            V[1, job] = job
                            V[2, job] = M
                            V[3, job] = j
                            V[4, job] = H
                        end

                        Cmax[M] -= C
                        filter!(x -> !(x in U[job][1:end-1]), sol[M])
                    end
                end
            end
        end

        L = sortperm(V[4, 1:end])

        if length(L) >= RLS
            r::Int8 = rand(1:RLS)
        else
            r = 1
        end
        
        POS::Int16 = V[1, L[r]]
        MACH::Int8 = V[2, L[r]]
        INS::Int16 = V[3, L[r]]
        SU::Int16 = length(U[POS])

        if SU == 1

            insert!(sol[MACH], INS, U[POS][1])
            deleteat!(U, POS)
            Cmax[MACH] = MachineSpan(MACH, p, S, sol)
            eval += 1

        elseif SU > 1

            if INS == 1

                for ins in 1:SU-1
                    insert!(sol[MACH], ins, U[POS][ins])
                end

            elseif INS == 2

                append!(sol[MACH], U[POS][1:SU-1])

            end

            deleteat!(U, POS)
            Cmax[MACH] = MachineSpan(MACH, p, S, sol)
            eval += 1
        end

        V = V[:, 1:end .!= L[r]]

        len -= 1
    end
    
    return(sol, Cmax, eval)
end

function UpdatePopulation(POP::Vector{Ind}, sol::Vector{Vector{Int16}}, Cmax::Vector{Int32},
    WPOS::Int8, m::Int8)
    #----- Updates the current population 

    for i in 1:m
        size::Int16 = length(POP[WPOS].Sol[i])

        while size != 0 
            popfirst!(POP[WPOS].Sol[i])
            size -= 1
        end

        push!(POP[WPOS].Sol[i], -1)

        for j in eachindex(sol[i])
            push!(POP[WPOS].Sol[i], sol[i][j])
        end

        push!(POP[WPOS].Sol[i], -2)
        POP[WPOS].OF[i] = Cmax[i]
    end

    POP[WPOS].Fit = maximum(Cmax)
end

function UpdateCoefficient(CoefCount::Int8)
    #----- Updates the coefficient value

    Coef::Float16 = 1 - 1/(2^CoefCount)
    
    return(Coef)
end

function Main_FSS(m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, t::Int)
    #----- Parameter declaration

    RLS::Int8 = 2 # Greedy factor
    MaxLen::Int8 = 5 # Maximal length of the path in RELP neighborhood
    Psize::Int8 = 100 # Population size
    k::Int8 = 20 # Number of solutions selected from the N solutions 
    N::Int8 = 100 # Set of best solutions 
    M::Int8 = 10 # Set of solutions to obtain the base solution 
    Stag::Int8 = 100 # Number of iterations with base solutions of the same size
    Iter::Int16 = 1 # Counter for the number of iterations without improvement
    MaxCoef::Int8 = 2 # Maximum allowed coefficient changes
    CoefCount::Int8 = 1 # Counter that calculates the coefficient value for an iteration
    I::Int64 = 0 # Counter for the total number of iterations
    NI::Int64 = 0 # Counter for objective function evaluations

    #----- Initializes the population 

    POP = InitialPopulation(Psize, RLS, MaxLen, m, n, p, S)
    Best::Int32 = minimum(j -> j.Fit, POP)

    #----- Start coefficient value

    Coef = UpdateCoefficient(CoefCount)

    #----- Definition of time variables

    Tmax::Float64 = convert(Float64, n) * convert(Float64, m) * convert(Float64, t)/2000
    elapsed::Float64 = 0
    ST::Float64 = time()
    tbest::Float64 = 0.0   # en iyiyi bulma ani (sn)

    while elapsed <= Tmax
        #----- Generates the fixed set

        AP = FixedSet(POP, k, N, M, Coef, m, n)

        #----- Randomized Greedy algorithm with preselected elements

        sol, Cmax, ev = RGF(AP, RLS, m, n, p, S)
        NI += ev

        NI += LocalSearch(sol, Cmax, m, p, S, MaxLen)

        #----- Update population

        W::Int32 = maximum(j -> j.Fit, POP)
        
        if maximum(Cmax) < W
            WPOS::Int8 = 0

            for i in 1:Psize
                if POP[i].Fit == W
                    WPOS = i
                    break
                end
            end

            UpdatePopulation(POP, sol, Cmax, WPOS, m)
        end

        #----- Check if a new global best was found

        if maximum(Cmax) < Best
            Best = maximum(Cmax)
            Iter = 1
            tbest = time() - ST
        else
            Iter += 1
        end

        #----- Update the coefficient value 
    
        if Iter >= Stag
            CoefCount += 1
            Iter = 1
    
            if CoefCount >= MaxCoef
                CoefCount = 1 
            end
    
            Coef = UpdateCoefficient(CoefCount)
        end

        I += 1
        elapsed = time() - ST
    end
    
    return(Best, I, NI, tbest)
end