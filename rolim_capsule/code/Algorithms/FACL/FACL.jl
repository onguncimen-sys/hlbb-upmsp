#=
* Implementation of the Firefly Algorithm with Courtship Learning (FACL) of Huang et al.
* Journal of Cloud Computing 11 (2022) 9 
* Problem: Unrelated parallel machine scheduling with sequence-dependent setup times
* Objective: Makespan
* Coded by Gustavo Alencar Rolim - Universidade de São Paulo (2022/2023)
=#

mutable struct Ind
    X::Vector{Float64} # Solution encoding
    MA::Vector{Int8} # Machine assignement
    JA::Matrix{Int16} # Job assignement
    Fit::Int32 # Fitness

    Ind() = new(Vector{Float64}[], Vector{Int8}[], Matrix{Int16}(undef, 0, 0), 0)
end

function Makespan(JA::Matrix{Int16}, m::Int8,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Calculates the makespan value 
    
    Cmax::Int32 = 0

    for i::Int8 in 1:m
        len = count(x -> x != 0, JA[i, :])
        span::Int32 = 0

        for j::Int16 in 1:len
            if j != len
                span += p[i, JA[i, j]] + S[i][JA[i, j], JA[i, j+1]]
            else
                span += p[i, JA[i, j]]
            end
        end

        if Cmax < span
            Cmax = span
        end
    end

    return(Cmax)
end

function JobAssign(JA::Matrix{Int16}, MA::Vector{Int8}, X::Vector{Float64},
    m::Int8, n::Int16)
    #----- Sequence the jobs in each machine

    RP = Vector{Float64}[[] for i::Int8 in 1:m] # Relative position 
    JP = Vector{Int16}[[] for i::Int8 in 1:m] # Saves the job index for sequencing

    for i::Int8 in 1:m 
        for j::Int16 in 1:n
            if MA[j] == i
                push!(RP[i], X[j])
                push!(JP[i], j)
            end
        end
    end

    for i::Int8 in 1:m 
        JP[i] = JP[i][sortperm(RP[i])]
    end

    for i::Int8 in 1:m
        C::Int16 = 1
        for j::Int16 in eachindex(JP[i])
            JA[i, C] = JP[i][j]
            C += 1
        end
    end
end

function InitPop(Np::Int8, UB::Int8, LB::Int8, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Initializes population

    POP = Ind[]

    for i::Int8 in 1:Np
        push!(POP, Ind())
        POP[i].X = zeros(Float64, n)
        POP[i].MA = zeros(Int8, n)
        POP[i].JA = zeros(Int16, m, n)

        for j::Int16 in 1:n
            POP[i].X[j] = LB + rand(Float64)*(UB-LB)
            POP[i].MA[j] = floor(POP[i].X[j])
        end

        JobAssign(POP[i].JA, POP[i].MA, POP[i].X, m, n)
        POP[i].Fit = Makespan(POP[i].JA, m, p, S)
    end

    return(POP)
end

function UpdatePosition(POP::Vector{Ind}, Xnew::Ind, i::Int8, j::Int8, UB::Int8, LB::Int8,
    alpha::Float16, beta::Int8, gamma::Int8, m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}})
    #----- Move solution i towards j

    Rij::Float64 = 0

    for a::Int16 in 1:n # Cartesian distance
        Rij += (POP[i].X[a] - POP[j].X[a])^2
    end

    Bij::Float64 = beta * exp(-gamma * Rij)
    epsilon::Float64 = rand(Float16) - 0.5
    scale::Int8 = UB - LB

    for a::Int16 in 1:n 
        Xnew.X[a] = POP[i].X[a] + Bij * (POP[j].X[a] - POP[i].X[a]) + alpha * epsilon * scale

        if Xnew.X[a] >= UB 
            Xnew.X[a] = UB - 1
        elseif Xnew.X[a] < LB 
            Xnew.X[a] = LB
        end

        Xnew.MA[a] = floor(Xnew.X[a])
    end

    JobAssign(Xnew.JA, Xnew.MA, Xnew.X, m, n)
    Xnew.Fit = Makespan(Xnew.JA, m, p, S)
end

function Reset(Xnew::Ind)
    #----- Updates the incumbent solution 

    Xnew.X = Xnew.X .* 0
    Xnew.MA = Xnew.MA .* 0
    Xnew.JA = Xnew.JA .* 0 
    Xnew.Fit = 0
end

function RouletteSelection(Archive::Vector{Ind}, Np::Int8)
    #----- Applies the roulette selection

    Idx::Int8 = 0
    Csum::Float64 = 0
    R = rand(Float64)
    Total::Float64 = sum(x -> 1/x.Fit, Archive)

    for i::Int16 in 1:Np
        Csum += (1/Archive[i].Fit)/Total

        if Csum >= R 
            Idx = i
            break
        end
    end

    if Idx == 0 
        Idx = Np
    end
    
    return(Idx)
end

function UpdatePositionCL(POP::Vector{Ind}, Xnew::Ind, j::Int8, k::Int8, UB::Int8, LB::Int8,
    alpha::Float16, m::Int8, n::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Move solution j towards k with courtship learning 

    Rij::Float16 = 0
   
    for a::Int16 in 1:n # Iterates over the dimension
        Rij += (POP[k].X[a] - POP[j].X[a])^2
    end

    Fkj::Float16 = 1/(pi*(Rij+1))
    epsilon::Float16 = rand(Float16) - 0.5
    scale::Int8 = UB - LB

    for a::Int16 in 1:n 
        Xnew.X[a] = POP[j].X[a] + Fkj * (POP[k].X[a] - POP[j].X[a]) + alpha * epsilon * scale

        if Xnew.X[a] >= UB 
            Xnew.X[a] = UB - 1
        elseif Xnew.X[a] < LB 
            Xnew.X[a] = LB
        end

        Xnew.MA[a] = floor(Xnew.X[a])
    end

    JobAssign(Xnew.JA, Xnew.MA, Xnew.X, m, n)
    Xnew.Fit = Makespan(Xnew.JA, m, p, S)
end

function UpdateArchive(POP::Vector{Ind}, Archive::Vector{Ind}, Np::Int8)
    #----- Updates the archive if a new best solution is found and if it is not repeated

    NEW::Bool = true
    posw::Int8 = 0 
    posb::Int8 = 0 
    Best = minimum(x -> x.Fit, POP)
    Worst = maximum(x -> x.Fit, Archive)

    for i::Int8 in 1:Np
        if Best == Archive[i].Fit
            NEW = false 
        end
        if POP[i].Fit == Best 
            posb = i
        end
        if Archive[i].Fit == Worst
            posw = i 
        end
    end

    if NEW == true 
        Archive[posw].X .= POP[posb].X
        Archive[posw].MA .= POP[posb].MA
        Archive[posw].JA .= POP[posb].JA
        Archive[posw].Fit = POP[posb].Fit
    end
end

function Main_FACL(m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, t::Int)
    #----- Parameter declaration

    Np::Int8 = 50
    beta::Int8 = 2 
    gamma::Int8 = 1
    alpha::Float16 = 0.3
    UB::Int8 = m+1
    LB::Int8 = 1
    I::Int64 = 0
    NI::Int64 = 0

    #----- Initializes the population and the archive

    POP = InitPop(Np, UB, LB, m, n, p, S)
    Archive = InitPop(Np, UB, LB, m, n, p, S)

    #----- Determine the best solution from population 

    B1 = minimum(x -> x.Fit, POP)
    B2 = minimum(x -> x.Fit, Archive)
    B = min(B1, B2)

    #----- Initializes the incumbent solution

    Xnew = Ind()
    Xnew.X = zeros(Float64, n)
    Xnew.MA = zeros(Int8, n)
    Xnew.JA = zeros(Int16, m, n)

    #----- Determine the time variables 

    Tmax = convert(Float64, n) * convert(Float64, m) * convert(Float64, t)/2000
    elapsed::Float64 = 0
    ST::Float64 = time()

    while elapsed <= Tmax
        for i::Int8 in 1:Np
            for j::Int8 in 1:Np
                if POP[j].Fit < POP[i].Fit
                    #----- Generate a new solution
    
                    UpdatePosition(POP, Xnew, i, j, UB, LB,
                    alpha, beta, gamma, m, n, p, S)
                    NI += 1
    
                    #----- Update population
    
                    if Xnew.Fit < POP[i].Fit
                        POP[i].X .= Xnew.X
                        POP[i].MA .= Xnew.MA
                        POP[i].JA .= Xnew.JA
                        POP[i].Fit = Xnew.Fit
    
                        if Xnew.Fit < B 
                            B = Xnew.Fit
                        end
                    end
                    
                    #----- Reset Xnew
    
                    Reset(Xnew)
                else
                    #----- Applies roulette selection
    
                    k = RouletteSelection(Archive, Np)
    
                    if POP[k].Fit < POP[j].Fit
                        #----- Generate a new solution
                        
                        UpdatePositionCL(POP, Xnew, j, k, UB, LB,
                        alpha, m, n, p, S)
                        NI += 1
    
                        #----- Update population
    
                        if Xnew.Fit < POP[i].Fit
                            POP[i].X .= Xnew.X
                            POP[i].MA .= Xnew.MA
                            POP[i].JA .= Xnew.JA
                            POP[i].Fit = Xnew.Fit
                            
                            if Xnew.Fit < B 
                                B = Xnew.Fit
                            end
                        end
    
                        #----- Reset Xnew
    
                        Reset(Xnew)
                    end
                end
            end
    
            #----- Update the archive
            UpdateArchive(POP, Archive, Np)
        end

        I += 1
        elapsed = time() - ST
    end
    
    return(B, I, NI)
end