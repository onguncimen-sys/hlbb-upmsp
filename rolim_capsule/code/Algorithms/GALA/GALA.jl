#=
* Implementation of the Genetic Algorithm with Local Search (GALA) of Eroglu et al.
* International Journal of Production Research 52 (19) (2014) 5841–5856
* Problem: Unrelated parallel machine scheduling with sequence-dependent setup times
* Objective: Makespan
* Coded by Gustavo Alencar Rolim - Universidade de São Paulo (2022/2023)
=#

mutable struct Ind
    Sol::Vector{Float64}
    Fit::Int32 

    Ind() = new(Vector{Float64}[], 0)
end

function Decode(IND::Vector{Float64}, m::Int8, n::Int16)
    #----- Decodes the chromossome

    job::Int16 = 1
    key = Vector{Float64}[[] for i in 1:m]
    sol = Vector{Int16}[[] for i in 1:m]
    A::Float64 = Inf
    M::Int8 = 1
    mach::Int8 = 1

    for i in 1:n*m
        if IND[i] < A
            A = IND[i]
            mach = M
        end

        M += 1

        if i % m == 0 
            push!(sol[mach], job)
            push!(key[mach], A)
            A = Inf
            M = 1
            job += 1
        end
    end

    for i in 1:m 
        sol[i] = sol[i][sortperm(key[i])]
    end
    
    return(sol)
end

function MachineSpan(mach::Int8, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, sol::Vector{Vector{Int16}})
    #----- Calculates and returns the span of a machine

    span::Int32 = 0
    size::Int16 = length(sol[mach])

    for i in eachindex(sol[mach])
        if i != size
            span += p[mach, sol[mach][i]] + S[mach][sol[mach][i], sol[mach][i+1]]
        else
            span += p[mach, sol[mach][i]]
        end
    end
    
    return(span)
end

function Fitness(IND::Vector{Float64}, m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}})
    #----- Calculates the fitness value of the solution

    sol = Decode(IND, m, n)
    Cmax::Int32 = 0

    for i::Int8 in 1:m
        span::Int32 = MachineSpan(i, p, S, sol)
        if span > Cmax 
            Cmax = span
        end
    end
    
    return(Cmax)
end

function InitialPopulation(m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, Psize::Int8)
    #----- Generates initial population
    
    POP = Ind[]

    for i::Int8 in 1:Psize 
        push!(POP, Ind())
        POP[i].Sol = rand(Float64, n*m)
        POP[i].Fit = Fitness(POP[i].Sol, m, n, p, S)
    end
        
    return(POP)
end

function Selection(Psize::Int8)
    #----- Selection of parents for crossover 

    r1::Int8 = rand(1:Psize)
    r2::Int8 = rand(1:Psize)

    while r1 == r2
        r2 = rand(1:Psize)
    end

    return(r1, r2)
end

function UpdateSolution(POP::Vector{Ind}, O::Vector{Float64}, m::Int8,
    n::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Update the old solution with a new one

    Cmax::Int32 = Fitness(O, m, n, p, S)
    W::Int32 = -1
    POS::Int8 = 0
    eval::Int64 = 1

    for i::Int8 in eachindex(POP)
        Max = POP[i].Fit

        if Max > W 
            W = Max
            POS = i
        end
    end
    
    if Cmax < POP[POS].Fit
        POP[POS].Sol .= O
        POP[POS].Fit = Cmax
    end

    return(eval)
end

function Crossover(POP::Vector{Ind}, Psize::Int8, Pc::Float16, m::Int8,
    n::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Performs crossover

    R = rand(Float64)
    eval::Int64 = 0

    if R <= Pc 
        r1, r2 = Selection(Psize)
        P1 = POP[r1].Sol
        P2 = POP[r2].Sol
        Cpos::Int16 = rand(2:n*m-1)
        O1 = zeros(Float64, n*m)
        O2 = zeros(Float64, n*m)

        for i in 1:n*m 
            if i <= Cpos
                O1[i] = P1[i]
                O2[i] = P2[i]
            else
                O1[i] = P2[i]
                O2[i] = P1[i]
            end
        end
        
        UpdateSolution(POP, O1, m, n, p, S)
        UpdateSolution(POP, O2, m, n, p, S)
        eval += 2
    end

    return(eval)    
end

function Mutation(POP::Vector{Ind}, Psize::Int8, Pm::Float16, m::Int8,
    n::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Performs mutation

    eval::Int64 = 0

    for i in 1:Psize
        R = rand(Float64)

        if R <= Pm
            #----- Substitute one random gene

            pos::Int16 = rand(1:n*m)
            NG = rand(Float64)
            POP[i].Sol[pos] = NG
            
            #----- Evaluate new solution 
            
            POP[i].Fit = Fitness(POP[i].Sol, m, n, p, S)
            eval += 1
        end
    end
    
    return(eval)
end

function DecodeGene(IND::Vector{Float64}, m::Int8, n::Int16)
    #----- Decode gene for local search

    job::Int16 = 1
    key = Vector{Float64}[[] for i in 1:m]
    sol = Vector{Int16}[[] for i in 1:m]
    A::Float64 = Inf
    M::Int8 = 1
    mach::Int8 = 1

    for i in 1:n*m
        if IND[i] < A
            A = IND[i]
            mach = M
        end

        M += 1

        if i % m == 0 
            push!(sol[mach], job)
            push!(key[mach], A)
            A = Inf
            M = 1
            job += 1
        end
    end

    for i in 1:m 
        sol[i] = sol[i][sortperm(key[i])]
    end

    GENE = zeros(Int16, 2, n)

    for i in 1:m
        count::Int16 = 1
        for j in sol[i]
            GENE[1, j] = i
            GENE[2, j] = count
            count += 1
        end
    end

    return(sol, GENE)
end

function InterMachine(GENE::Matrix{Int16}, sol::Vector{Vector{Int16}}, j::Int16, k::Int16,
    S::Vector{Matrix{Int16}})
    #----- Calculates the values of the dominance property

    M::Int8 = GENE[1, j]
    Calc::Int32 = 0
    pos1::Int16 = 0
    pos2::Int16 = 0
    job1::Int16 = 0
    job2::Int16 = 0
    nxt::Int16 = 0 
    prv::Int16 = 0

    if GENE[2, j] == GENE[2, k] + 1 || GENE[2, j] + 1 == GENE[2, k] # Adjacent jobs 
        if GENE[2, j] > GENE[2, k]
            pos1 = GENE[2, k]
            job1 = k
            pos2 = GENE[2, j]
            job2 = j
        else
            pos1 = GENE[2, j]
            job1 = j
            pos2 = GENE[2, k]
            job2 = k
        end

        if GENE[2, j] == 1 || GENE[2, k] == 1
            if length(sol[M]) > 2
                nxt = sol[M][pos2+1]
                Calc = (S[M][job2, job1] - S[M][job1, job2]) + (S[M][job1, nxt] - S[M][job2, nxt])
            else
                Calc = (S[M][job2, job1] - S[M][job1, job2])
            end
        elseif GENE[2, j] == length(sol[M]) || GENE[2, k] == length(sol[M])
            if length(sol[M]) > 2
                prv = sol[M][pos1-1]
                Calc = (S[M][prv, job2] - S[M][prv, job1]) + (S[M][job2, job1] - S[M][job1, job2])
            else
                Calc = (S[M][job2, job1] - S[M][job1, job2])
            end
        else
            nxt = sol[M][pos2+1]
            prv = sol[M][pos1-1]
            Calc = (S[M][prv, job2] - S[M][prv, job1]) + (S[M][job2, job1] - S[M][job1, job2]) + 
            (S[M][job1, nxt] - S[M][job2, nxt])
        end    

    else # Non-adjacent jobs
        if GENE[2, j] > GENE[2, k]
            pos1 = GENE[2, k]
            job1 = k
            pos2 = GENE[2, j]
            job2 = j
        else
            pos1 = GENE[2, j]
            job1 = j
            pos2 = GENE[2, k]
            job2 = k
        end

        if pos1 == 1 && pos2 == length(sol[M])

            nxt1::Int32 = sol[M][pos1+1]
            prv2::Int32 = sol[M][pos2-1]
            Calc = (S[M][job2, nxt1] - S[M][job1, nxt1]) + (S[M][prv2, job1] - S[M][prv2, job2])

        elseif pos1 == 1 && pos2 < length(sol[M])

            nxt1 = sol[M][pos1+1]
            prv2 = sol[M][pos2-1]
            nxt2::Int32 = sol[M][pos2+1]
            Calc = (S[M][job2, nxt1] - S[M][job1, nxt1]) + (S[M][prv2, job1] - S[M][prv2, job2]) + 
            (S[M][job1, nxt2] - S[M][job2, nxt2])

        elseif pos1 > 1 && pos2 == length(sol[M])

            nxt1 = sol[M][pos1+1]
            prv2 = sol[M][pos2-1]
            prv1::Int32 = sol[M][pos1-1]
            Calc = (S[M][prv1, job2] - S[M][prv1, job1]) + (S[M][job2, nxt1] - S[M][job1, nxt1]) + 
            (S[M][prv2, job1] - S[M][prv2, job2])

        else

            nxt1 = sol[M][pos1+1]
            prv1 = sol[M][pos1-1]
            nxt2 = sol[M][pos2+1]
            prv2 = sol[M][pos2-1]
            Calc = (S[M][prv1, job2] - S[M][prv1, job1]) + (S[M][job2, nxt1] - S[M][job1, nxt1]) + 
            (S[M][prv2, job1] - S[M][prv2, job2]) + (S[M][job1, nxt2] - S[M][job2, nxt2])

        end
    end

    return(Calc)
end

function UpdateInter(IND::Vector{Float64}, GENE::Matrix{Int16},
    sol::Vector{Vector{Int16}}, j::Int16, k::Int16, m::Int8,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- If the movement is accepted, updates the individual

    M::Int8 = GENE[1, j]
    temp1::Int16 = GENE[2, j] 
    temp2::Int16 = GENE[2, k]
    GENE[2, j] = temp2
    GENE[2, k] = temp1
    sol[M][temp1] = k 
    sol[M][temp2] = j

    #----- Updates the random keys

    pos1::Int16 = (j*m-m+1)+(M-1)
    pos2::Int16 = (k*m-m+1)+(M-1)
    RK1::Float64 = IND[pos1]
    RK2::Float64 = IND[pos2]

    IND[pos1] = RK2
    IND[pos2] = RK1

    ref1::Int16 = j*m-m+1
    ref2::Int16 = k*m-m+1

    for i in ref1:ref1+m-1
        if IND[i] != RK2
            if IND[i] <= RK2
                r = rand(Float64)

                    while r <= RK2
                        r = rand(Float64)
                    end

                IND[i] = r
            end
        end
    end

    for i in ref2:ref2+m-1
        if IND[i] != RK1
            if IND[i] <= RK1
                r = rand(Float64)

                    while r <= RK1
                        r = rand(Float64)
                    end

                IND[i] = r 
            end
        end
    end

    #----- Calculates the new value of the Objective function

    Cmax::Int32 = 0

    for i::Int8 in 1:m
        span::Int32 = MachineSpan(i, p, S, sol)
        if span > Cmax 
            Cmax = span
        end
    end
    
    return(Cmax)
end

function IntraMachine(GENE::Matrix{Int16}, sol::Vector{Vector{Int16}},
    j::Int16, k::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Calculates the values of the dominance property for different machines
    
    M1::Int8 = GENE[1, j]
    M2::Int8 = GENE[1, k]
    pos1::Int16 = GENE[2, j]
    pos2::Int16 = GENE[2, k]
    job1::Int16 = j 
    job2::Int16 = k 
    Cmax1::Int32 = MachineSpan(M1, p, S, sol)
    Cmax2::Int32 = MachineSpan(M2, p, S, sol)
    Cmax::Int32 = max(Cmax1, Cmax2)
    Calc::Bool = false
    prv1::Int16 = 0 
    prv2::Int16 = 0 
    nxt1::Int16 = 0 
    nxt2::Int16 = 0
    a::Int32 = 0 
    b::Int32 = 0 
    c::Int32 = 0 
    d::Int32 = 0

    if length(sol[M1]) <= 1 || length(sol[M2]) <= 1 
        return(Calc)
    end
    
    if pos1 == 1
        nxt1 = sol[M1][pos1+1]
        b = S[M1][job2, nxt1] - S[M1][job1, nxt1]
    elseif pos1 == length(sol[M1])
        prv1 = sol[M1][pos1-1]
        a = S[M1][prv1, job2] - S[M1][prv1, job1]
    else
        prv1 = sol[M1][pos1-1]
        nxt1 = sol[M1][pos1+1]
        a = S[M1][prv1, job2] - S[M1][prv1, job1]
        b = S[M1][job2, nxt1] - S[M1][job1, nxt1]
    end

    if pos2 == 1
        nxt2 = sol[M2][pos2+1]
        d = S[M2][job1, nxt2] - S[M2][job2, nxt2]
    elseif pos2 == length(sol[M2])
        prv2 = sol[M2][pos2-1]
        c = S[M2][prv2, job1] - S[M2][prv2, job2]
    else
        prv2 = sol[M2][pos2-1]
        nxt2 = sol[M2][pos2+1]
        c = S[M2][prv2, job1] - S[M2][prv2, job2]
        d = S[M2][job1, nxt2] - S[M2][job2, nxt2]
    end

    if max(Cmax1 + a + b, Cmax2 + c + d) < Cmax
        Calc = true
    end
    
    return(Calc)
end

function UpdateIntra(IND::Vector{Float64}, GENE::Matrix{Int16}, sol::Vector{Vector{Int16}},
    j::Int16, k::Int16, m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- If the movement is accepted, updates the individual

    M1::Int8 = GENE[1, j]
    M2::Int8 = GENE[1, k]
    GENE[1, k] = M1
    GENE[1, j] = M2
    Temp1::Int16 = GENE[2, j]
    Temp2::Int16 = GENE[2, k]
    GENE[2, k] = Temp1
    GENE[2, j] = Temp2
    sol[M1][Temp1] = k
    sol[M2][Temp2] = j

    #----- Updates the random keys
    
    pos1::Int16 = (j*m-m+1)+(M1-1)
    pos2::Int16 = (k*m-m+1)+(M2-1)
    RK1::Float64 = IND[pos1]
    RK2::Float64 = IND[pos2]
    inspos1::Int16 = (j*m-m+1)+(M2-1)
    inspos2::Int16 = (k*m-m+1)+(M1-1)

    IND[inspos1] = RK2
    IND[inspos2] = RK1

    ref1::Int16 = j*m-m+1
    ref2::Int16 = k*m-m+1

    for i in ref1:ref1+m-1
        if IND[i] != RK2
            if IND[i] <= RK2
                r = rand(Float64)

                    while r <= RK2
                        r = rand(Float64)
                    end

                IND[i] = r
            end
        end
    end

    for i in ref2:ref2+m-1

        if IND[i] != RK1
            if IND[i] <= RK1
                r = rand(Float64)

                    while r <= RK1
                        r = rand(Float64)
                    end

                IND[i] = r 
            end
        end
    end
    
    #----- Calculates the new value of the Objective function

    Cmax::Int32 = 0

    for i::Int8 in 1:m
        span::Int32 = MachineSpan(i, p, S, sol)
        if span > Cmax 
            Cmax = span
        end
    end
    
    return(Cmax)
end

function LocalSearch(POP::Vector{Ind}, Psize::Int8, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Performs the local search

    eval::Int64 = 0 

    for i in 1:Psize
        sol, GENE = DecodeGene(POP[i].Sol, m, n)

        for j::Int16 in 1:n-1 
            k::Int16 = j+1

            if GENE[1, j] == GENE[1, k] # Inter-machine interchange 
                Calc1 = InterMachine(GENE, sol, j, k, S)
                
                if Calc1 < 0
                    POP[i].Fit = UpdateInter(POP[i].Sol, GENE, sol, j, k, m, p, S)
                    eval += 1
                    break 
                end
            else # Intra-machine exchange
                Calc2 = IntraMachine(GENE, sol, j, k, p, S)

                if Calc2 == true
                    POP[i].Fit = UpdateIntra(POP[i].Sol, GENE, sol, j, k, m, p, S)
                    eval += 1
                    break
                end
            end
        end
    end
    
    return(eval)
end

function Main_GALA(m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, t::Int)
    #----- Definition of parameters

    Psize::Int8 = 100 
    Pc::Float16 = 1.0 
    Pm::Float16 = 0.2
    I::Int64 = 1
    NI::Int64 = 0

    #----- Initialization of the algorithm

    POP = InitialPopulation(m, n, p, S, Psize)
    NI += Psize

    B = minimum(j -> j.Fit, POP)
    
    #----- Definition of time variables

    Tmax = convert(Float64, n) * convert(Float64, m) * convert(Float64, t)/2000
    elapsed::Float64 = 0
    ST::Float64 = time()
    
    while elapsed <= Tmax
        #----- Apply crossover operator

        eval = Crossover(POP, Psize, Pc, m, n, p, S)
        NI += eval 

        #----- Apply mutation operator

        eval = Mutation(POP, Psize, Pm, m, n, p, S)
        NI += eval 

        #----- Apply local search

        eval = LocalSearch(POP, Psize, m, n, p, S)
        NI += eval

        #----- Update the best solution 

        INC = minimum(j -> j.Fit, POP)

        if INC < B
            B = INC
        end
    
        I += 1
        elapsed = time() - ST
    end
    
    return(B, I, NI)
end