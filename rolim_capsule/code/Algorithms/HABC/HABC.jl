#=
* Implementation of the Hybrid Artifical Bee Colony (HABC) Algorithm of Lin & Ying
* Computers & Operations Research 51 (2014) 172–181
* Problem: Unrelated parallel machine scheduling with sequence-dependent setup times
* Objective: Makespan
* Coded by Gustavo Alencar Rolim - Universidade de São Paulo (2022/2023)
=#

using Random

mutable struct Ind
    Sol::Vector{Int16}
    Fit::Int32
    LIM::Int16

    Ind() = new(Vector{Int16}[], 0, 0)
end

function Init_Temperature(m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Calculation of the initial temperature

    PT = zeros(Float64, m, n)

    for i in 1:m 
        for j in 1:n
            SUMS::Float64 = 0

            for k in 1:n
                SUMS += S[i][j,k]
            end

            SUMS /= n 
            PT[i,j] = p[i,j]+SUMS
        end 
    end

    SPT::Float64 = sum(PT)
    T0::Float64 = 0.25*SPT/(n*m)

    return(T0)
end

function Makespan(sol::Vector{Int16}, m::Int8, p::Matrix{Int16},
    S::Vector{Matrix{Int16}})
    #----- Calculates the inversely proportional fitness

    CT = zeros(Int32, m)
    count::Int16 = 1 
    
    for i in eachindex(sol)
        if sol[i] == 0
            count += 1
        else
            if i != length(sol)
                if sol[i+1] != 0
                    CT[count] += p[count, sol[i]]+S[count][sol[i],sol[i+1]]
                else
                    CT[count] += p[count, sol[i]]
                end
            else
                CT[count] += p[count, sol[i]]
            end
        end
    end
    
    Cmax::Int32 = maximum(CT)

    return(Cmax)
end

function Init_Population(Psize::Int8, m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}})
    #----- Initializes the population

    POP = Ind[]
    U = collect(Int16, 1:n)

    for i in 1:Psize
        push!(POP, Ind())
        append!(POP[i].Sol, U)
        
        for j in 1:m-1
            push!(POP[i].Sol, 0)
        end

        shuffle!(POP[i].Sol)
        POP[i].Fit = Makespan(POP[i].Sol, m, p, S)
    end

    return(POP)
end

function Bottleneck(sol::Vector{Int16}, fit::Int32, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Identification of bottleneck machines from a solution

    CT = zeros(Int32, m)
    BM = Int8[] # Saves the indices of bottleneck machines
    count::Int16 = 1

    for i in 1:n+m-1
        if sol[i] == 0
            count += 1
        else
            if i != n+m-1
                if sol[i+1] != 0
                    CT[count] += p[count, sol[i]] + S[count][sol[i],sol[i+1]]
                else
                    CT[count] += p[count, sol[i]]

                    if CT[count] == fit
                        push!(BM, count)
                    end
                end
            else
                CT[count] += p[count, sol[i]]

                if CT[count] == fit
                    push!(BM, count)
                end
            end
        end
    end

    return(BM)
end

function Begin_End(Ref::Int8, sol::Vector{Int16}, m::Int8)
    #----- Returns the beginning and end of a machine sequence

    mach::Int8 = 1 # Machine counter
    count::Int16 = 1 # Position counter
    first::Int16 = 0 # Marks the beginning of the machine
    last::Int16 = 0 # Marks the end of the machine

    #----- Finds the first job of the reference machine

    if Ref == 1
        first = 1
    else
        while mach != Ref
            if sol[count] == 0
                mach += 1
            end

            count += 1
        end

        first = count
    end

    #----- Finds the last job of the reference machine

    if Ref == m
        last = length(sol)
    else
        while sol[count+1] != 0
            count += 1
        end

        last = count
    end

    return(first, last)
end

function Destruction(BM::Vector{Int8}, Inc::Vector{Int16}, n::Int16, m::Int8)
    #----- Removes the jobs from the partial solution 

    RMV = Int16[] # Removed jobs
    alpha::Int8 = 0 # Parameter alpha
    count::Int8 = 0 # counter

    if length(BM) > 4
        alpha = length(BM)
    else
        alpha = 4
    end

    #----- Pick one job from each bottleneck machine

    for i::Int8 in BM 
        first, last = Begin_End(i, Inc, m)
        r::Int16 = rand(first:last)
        push!(RMV, Inc[r])
        deleteat!(Inc, r)
        count += 1 
    end

    #----- Remove the rest of the jobs randomly

    len::Int16 = n+m-1-count 

    while count < alpha
        r = rand(1:len)

        while Inc[r] == 0 
            r = rand(1:len)
        end 

        push!(RMV, Inc[r])
        deleteat!(Inc, r)
        len -= 1
        count += 1
    end

    return(RMV)
end

function Repair(RMV::Vector{Int16}, sol::Vector{Int16}, m::Int8,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Repair the solution 

    len::Int16 = length(RMV)
    Cmax::Int32 = 0
    eval::Int64 = 0 

    while len != 0
        pos::Int16 = 0
        Best::Int32 = 999999999

        for i::Int16 in 1:length(sol)+1
            insert!(sol, i, RMV[1])
            New_Cmax = Makespan(sol, m, p, S)
            eval += 1
            
            if New_Cmax < Best
                Best = New_Cmax
                pos = i
            end

            deleteat!(sol, i)
        end

        insert!(sol, pos, RMV[1])
        popfirst!(RMV)
        Cmax = Best
        len -= 1
    end

    return(Cmax, eval)
end

function IG_HABC(sol::Vector{Int16}, fit::Int32, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, Inc::Vector{Int16})
    #----- Generates neighborhood solutions using the iterated greedy method
    
    BM = Bottleneck(sol, fit, m, n, p, S) # BM represents the indices of bottleneck machines

    #----- Destruction phase

    RMV = Destruction(BM, Inc, n, m)

    #----- Insertion 

    Cmax, eval = Repair(RMV, sol, m, p, S)

    return(Cmax, eval)
end

function Swap(BM::Vector{Int8}, NBM::Int8, sol::Vector{Int16}, fit::Int32, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Applies the swap procedure

    eval::Int64 = 0

    if NBM == 2
        #----- Exchange the jobs between the two bottleneck machines 

        f1, l1 = Begin_End(BM[1], sol, m)
        f2, l2 = Begin_End(BM[2], sol, m)

        for i::Int16 in f1:l1
            job1::Int16 = sol[i]
    
            for j::Int16 in f2:l2
                job2::Int16 = sol[j]

                #---- Swap jobs

                sol[j] = job1
                sol[i] = job2

                #----- Evaluate the solution

                New_Cmax = Makespan(sol, m , p, S)
                eval += 1

                #----- Checks if the new solution is better than incumbent solution 

                if New_Cmax < fit 
                    fit = New_Cmax
                    i = f1
                    break
                else
                    sol[i] = job1
                    sol[j] = job2
                end
            end
        end
    else
        #----- Exchange the jobs between the bottleneck machine and the other machines

        f, l = Begin_End(BM[1], sol, m)

        for i::Int16 in f:l
            job1 = sol[i]

            for j::Int16 in 1:n+m-1
                if !(j >= f && j <= l)
                    if sol[j] != 0 
                        job2::Int16 = sol[j]

                        #---- Swap jobs
        
                        sol[j] = job1
                        sol[i] = job2
                        
                        #----- Evaluate the solution
        
                        New_Cmax = Makespan(sol, m , p, S)
                        eval += 1
        
                        #----- Checks if the new solution is better than incumbent solution 
        
                        if New_Cmax < fit 
                            fit = New_Cmax
                            i = f
                            break
                        else
                            sol[i] = job1
                            sol[j] = job2
                        end
                    end
                end
            end
        end
    end

    return(fit, eval)
end

function LocalSearch(sol::Vector{Int16}, fit::Int32, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Apply the local search procedure

    Cmax = fit
    BM = Bottleneck(sol, fit, m, n, p, S)
    NBM::Int8 = length(BM)
    eval::Int64 = 0

    if NBM > 2 
        return(Cmax, eval)
    else
        Cmax, eval = Swap(BM, NBM, sol, fit, m, n, p, S)
    end
    
    return(Cmax, eval)
end

function Employed_Bees(POP::Vector{Ind}, Psize::Int8, T::Float64,
    m::Int8, n::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}},
    Inc::Vector{Int16})
    #----- Place the employed bees on their food sources

    eval::Int64 = 0 

    for i::Int8 in 1:Psize
        Inc .= POP[i].Sol
        Cmax = POP[i].Fit

        #----- Apply Iterated Greedy 

        Cmax, ev = IG_HABC(Inc, Cmax, m, n, p, S, Inc)
        eval += ev

        #----- Apply Local Search

        Cmax, ev = LocalSearch(Inc, Cmax, m, n, p, S)
        eval += ev

        delta::Int32 = Cmax - POP[i].Fit

        if delta < 0

            POP[i].Sol .= Inc
            POP[i].Fit = Cmax

        else
            r = rand(Float64)
            POP[i].LIM += 1

            if r < exp(-delta/T)
                POP[i].Sol .= Inc
                POP[i].Fit = Cmax
            end
        end
    end

    return(eval)
end

function Select_Individual(POP::Vector{Ind}, Psize::Int8)
    #----- Apply the roulette wheel to select the incumbent solution 

    SF::Float64 = sum(j -> 1/j.Fit, POP) # Calculates the sum of fitness values
    r = rand(Float64) # Random number for roulette selection
    prob::Float64 = 0 # Cumulative probability 
    Select::Int8 = 0 # Selected individual 

    for i::Int8 in 1:Psize
        Ind_Fit::Float64 = 1/POP[i].Fit
        prob += Ind_Fit/SF

        if prob >= r
            Select = i
            break
        end
    end
    
    return(Select)
end

function Onlooker_Bees(POP::Vector{Ind}, Psize::Int8, T::Float64,
    m::Int8, n::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}}, 
    Inc::Vector{Int16})
    #----- Place the onlooker bees on the food sources

    eval::Int64 = 0 

    for i::Int8 in 1:Psize
        POS = Select_Individual(POP, Psize)
        Inc .= POP[POS].Sol
        Cmax = POP[POS].Fit

        #----- Apply Iterated Greedy 

        Cmax, ev = IG_HABC(Inc, Cmax, m, n, p, S, Inc)
        eval += ev

        #----- Apply Local Search
        
        Cmax, ev = LocalSearch(Inc, Cmax, m, n, p, S)
        eval += ev

        #----- Apply acceptance criterion
    
        delta::Int32 = Cmax - POP[POS].Fit

        if delta < 0 
            POP[i].Sol .= Inc
            POP[i].Fit = Cmax
                
        else
            r = rand(Float64)
            POP[i].LIM += 1
        
            if r < exp(-delta/T)
                POP[i].Sol .= Inc
                POP[i].Fit = Cmax
            end
        end
    end

    return(eval)
end

function Scout_Bees(POP::Vector{Ind}, Psize::Int8, limit::Int16,
    m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Send the scouts to search new food sources

    eval::Int64 = 0 

    for i in 1:Psize
        if POP[i].LIM >= limit
            shuffle!(POP[i].Sol)
            POP[i].Fit = Makespan(POP[i].Sol, m, p, S)
            eval += 1
            POP[i].LIM = 0
        end
    end
    
    return(eval)
end

function Main_HABC(m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, t::Int)
    #----- Definition of parameters

    Psize::Int8 = 10 # Population size
    limit::Int16 = 1000 # Maximum number of iterations without improvement
    beta::Float64 = 0.90 # Cooling factor
    G::Int64 = 1 # Generation counter
    NI::Int64 = 0 # Objective function evaluations 
    T = Init_Temperature(m, n, p, S) # Calculation of the initial temperature
    
    #----- Initialization of the algorithm

    POP = Init_Population(Psize, m, n, p, S)

    #----- Determine the initial best solution

    B = minimum(j -> j.Fit, POP)

    #----- Incumbent solution

    Inc = zeros(Int16, n+m-1)
        
    #----- Definition of time variables
    
    Tmax::Float64 = convert(Float64, n) * convert(Float64, m) * convert(Float64, t)/2000
    elapsed::Float64 = 0
    ST::Float64 = time()

    Tbest = 0

    while elapsed <= Tmax
        #----- Perform the employed bees phase

        NI += Employed_Bees(POP, Psize, T, m, n, p, S, Inc)

        #----- Perform the onlooker bees phase

        NI += Onlooker_Bees(POP, Psize, T, m, n, p, S, Inc)

        #----- Perform the scout bees phase

        NI += Scout_Bees(POP, Psize, limit, m, p, S)

        #----- Checks for the best solution

        Cmin = minimum(j -> j.Fit, POP)

        if Cmin < B 
            B = Cmin
            Tbest = time() - ST
        end

        #----- Update the temperature

        if G % limit == 0 
            T *= beta
        end

        G += 1
        elapsed = time() - ST
    end

    return(B, G, NI)
end