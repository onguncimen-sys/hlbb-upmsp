#=
* Implementation of the Whale Optimization Algorithm with Firefly Algorithm of Al-qaness et al.
* Soft Computing 25 (2021) 9545–9557
* Problem: Unrelated parallel machine scheduling with sequence-dependent setup times
* Objective: Makespan
* Coded by Gustavo Alencar Rolim - Universidade de São Paulo (2022/2023)
=#

using Distributions

mutable struct Ind
    X::Vector{Float64} # Solution encoding
    MA::Vector{Int8} # Machine assignement
    JA::Matrix{Int16} # Job assignement
    Fit::Int32 # Fitness 
    Pri::Float64 # Selection probability 

    Ind() = new(Vector{Float64}[], Vector{Int8}[], Matrix{Int16}(undef, 0, 0), 0, 0.0)
end

function Makespan(JA::Matrix{Int16}, m::Int8, p::Matrix{Int16},
    S::Vector{Matrix{Int16}})
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

function InitPop(N::Int8, UB::Int8, LB::Int8, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Initializes population

    POP = Ind[]

    for i::Int8 in 1:N
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

    #----- Updates probabilities

    Total = sum(x -> x.Fit, POP)

    for i::Int8 in 1:N 
        POP[i].Pri = POP[i].Fit/Total
    end

    return(POP)
end

function Reset(Xnew::Ind)
    #----- Resets the incumbent solution 

    Xnew.X = Xnew.X .* 0
    Xnew.MA = Xnew.MA .* 0
    Xnew.JA = Xnew.JA .* 0 
    Xnew.Fit = 999999999
end

function FA(P::Vector{Ind}, Idx::Int8, Xnew::Ind, beta::Int8, gamma::Int8,
    UB::Int8, LB::Int8, N::Int8, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Update the solution according to FA

    for i::Int8 in 1:N
        if P[i].Fit < P[Idx].Fit
            #----- Update the position of the new solution

            Rij::Float64 = 0

            for j::Int16 in 1:n
                Rij += (P[i].X[j] - P[Idx].X[j])^2
            end
            
            Bij::Float64 = beta * exp(-gamma * Rij)
            scale::Int8 = UB - LB

            for j::Int16 in 1:n
                ϵ = rand(Float64) - 0.5
                alpha = rand(Float64)
                Xnew.X[j] = P[Idx].X[j] + Bij * (P[Idx].X[j] - P[i].X[j]) + alpha * ϵ * scale

                if Xnew.X[j] >= UB
                    Xnew.X[j] = UB - 1
                elseif Xnew.X[j] < LB 
                    Xnew.X[j] = LB
                end
    
                Xnew.MA[j] = floor(Xnew.X[j])
            end
            
            JobAssign(Xnew.JA, Xnew.MA, Xnew.X, m, n)
            Xnew.Fit = Makespan(Xnew.JA, m, p, S)
            break
        end
    end
end

function BestInd(P::Vector{Ind}, N::Int8)
    #----- Returns the index of the best individual

    MIN::Int32 = P[1].Fit
    Idx::Int8 = 1

    for i::Int8 in 1:N 
        if P[i].Fit < MIN
            MIN = P[i].Fit
            Idx = i 
        end
    end

    return(Idx)
end

function WOA(P::Vector{Ind}, Idx::Int8, Xnew::Ind, a::Float64, b::Int8,
    UB::Int8, LB::Int8, N::Int8, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Update the solution according to WOA

    Pr = rand(Float64)
    r1 = rand(Float64)
    r2 = rand(Float64)

    A::Float64 = 2*a*r1-a 
    C::Float64 = 2*r2
    l = rand(Uniform(-1, 1))
    Best = BestInd(P, N)

    for i::Int16 in 1:n 
        if Pr < 0.5
            if abs(A) >= 1 
                k = rand(1:N)

                while k == Idx 
                    k = rand(1:N)
                end

                D = abs(C * P[k].X[i] - P[Idx].X[i])
                Xnew.X[i] = P[k].X[i] - A*D

            elseif abs(A) < 1
                D = abs(C * P[Best].X[i] - P[Idx].X[i])
                Xnew.X[i] = P[Best].X[i] - A*D
            end
        else
            D = abs(P[Best].X[i] - P[Idx].X[i])
            Xnew.X[i] = D*exp(b*l)*cos(2*pi*l)+P[Best].X[i]
        end

        if Xnew.X[i] >= UB 
            Xnew.X[i] = UB - 1
        elseif Xnew.X[i] < LB 
            Xnew.X[i] = LB
        end

        Xnew.MA[i] = floor(Xnew.X[i])
    end

    JobAssign(Xnew.JA, Xnew.MA, Xnew.X, m, n)
    Xnew.Fit = Makespan(Xnew.JA, m, p, S)
end

function Main_WOAFA(m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, t::Int)
    #----- Parameter declaration

    a::Float64 = 2.0
    b::Int8 = 1
    N::Int8 = 30
    beta::Int8 = 2 
    gamma::Int8 = 1
    UB::Int8 = m+1
    LB::Int8 = 1
    I::Int64 = 0
    NI::Int64 = 0

    #----- Initializes population

    P = InitPop(N, UB, LB, m, n, p, S)

    #----- Determine the current best solution 

    B::Int32 = minimum(j -> j.Fit, P)

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
        a = a - elapsed * a/Tmax
        
        for i::Int8 in 1:N
            if P[i].Pri >= 0.5

                FA(P, i, Xnew, beta, gamma, UB, LB, N, m, n, p, S)
                NI += 1

                if Xnew.Fit < P[i].Fit
                    P[i].X .= Xnew.X
                    P[i].MA .= Xnew.MA
                    P[i].JA .= Xnew.JA
                    P[i].Fit = Xnew.Fit

                    Total = sum(x -> x.Fit, P)

                    for j::Int8 in 1:N 
                        P[j].Pri = P[j].Fit/Total
                    end
                    
                    if Xnew.Fit < B 
                        B = Xnew.Fit
                    end
                end
                
                Reset(Xnew)      
            else
                #----- Update solution according to WOA
                
                WOA(P, i, Xnew, a, b, UB, LB, N, m, n, p, S)
                NI += 1
    
                if Xnew.Fit < P[i].Fit
                    P[i].X .= Xnew.X
                    P[i].MA .= Xnew.MA
                    P[i].JA .= Xnew.JA
                    P[i].Fit = Xnew.Fit

                    Total = sum(x -> x.Fit, P)

                    for j::Int8 in 1:N 
                        P[j].Pri = P[j].Fit/Total
                    end
                    
                    if Xnew.Fit < B 
                        B = Xnew.Fit
                    end
                end
                
                Reset(Xnew)
            end
        end

        I += 1
        elapsed = time() - ST
    end

    return(B, I, NI)
end